from typing import List, Optional
from fastapi import FastAPI, Header, Request, Form, Depends, HTTPException, status, APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from jose import JWTError, jwt
from itsdangerous import URLSafeTimedSerializer
from database import SessionLocal, engine
from models import Base, Server, Cashier, PasswordHistory, Cart, CartItem, Product, Discount, Payment
from models import Deal, DealItem, DealItemModifier, Modifier, CartDeal, CartDealItem, CartDealItemModifier
import bcrypt
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import pytz
from pydantic_models import CartItemCreate, CartResponse, CartItemResponse
import re
import uuid
from sqlalchemy import or_

# App and DB setup
app = FastAPI()
Base.metadata.create_all(bind=engine)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # points to backend/
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "../frontend")) # jinja template directory

# Constants and secret keys
JWT_SECRET = "FSYdwgdi313rvaqiq0UA28u4e1jbkdbugWDeqwubei2fe1eHBwrlpqwnriekep1AS"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 30
SECRET_KEY = "hviy2te61r23c1uy2ei7312eb1dujf9w8yw19327te87183r1hvdygqiywd8yq8d"
SECURITY_PASSWORD_SALT = "dcnow8ye483ruv31ig91ye9313wdhnqihdw0yrih2it"
IST = pytz.timezone('Asia/Kolkata')

# Dependencies
pwd_context = bcrypt

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Password utils
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def validate_password_complexity(password: str):
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$'
    if not re.match(pattern, password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long, include 1 uppercase, 1 lowercase, 1 number, and 1 special character.")

# JWT utils
def create_jwt_token(data: dict, expires_delta: timedelta = timedelta(minutes=JWT_EXPIRE_MINUTES)):
    to_encode = data.copy()
    expire = datetime.now(IST) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str): # decodes the token
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login-jwt") 

# it extracts token (from header, query or form)
async def get_current_user(
    request: Request,  # add request object to access query/form manually
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    # manual extraction from request
    form_token = None
    query_token = request.query_params.get("token")
    if request.method == "POST":
        form_token = (await request.form()).get("token")  # Optional if POST with hidden form field

    jwt_token = (
        query_token
        or form_token
        or (authorization.removeprefix("Bearer ") if authorization else None)
    )

    if not jwt_token:
        # raise HTTPException(401, "Token missing")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated: Token missing.",
                            headers={"WWW-Authenticate": "Bearer"})

    payload = decode_jwt_token(jwt_token) #token hota aadhi 
    if not payload:
        # raise HTTPException(status_code=401, detail="Invalid or expired token.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated: Invalid or expired token.",
                            headers={"WWW-Authenticate": "Bearer"})
    
    email = payload.get("sub")
    role = payload.get("role")
    if not email or not role:
        # raise HTTPException(status_code=401, detail="Token missing email or role.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated: Token missing email or role.",
                            headers={"WWW-Authenticate": "Bearer"})
    
    model = Server if role == "server" else Cashier
    user = db.query(model).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user

@app.get("/cashier-page", response_class=HTMLResponse)
def cashier_page(request: Request, user=Depends(get_current_user), token: str = Query(None)):
    if user.role != "cashier":
        raise HTTPException(status_code=403, detail="Access forbidden")
    return templates.TemplateResponse("cashier.html", {"request": request, "user": user, "token": token})

# @app.get("/server-page", response_class=HTMLResponse)
# def server_page(request: Request, user=Depends(get_current_user), token: str = Query(None)): # Add token as Query param
#     if user.role != "server":
#         raise HTTPException(status_code=403, detail="Access forbidden")
#     return templates.TemplateResponse("server.html", {"request": request, "user": user, "token": token}) # Pass token to template

# registration routes
@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...), gender: str = Form(...), role: str = Form(...), db: Session = Depends(get_db)):
    role = role.strip().lower()  # normalize
    if role not in ["server", "cashier"]:
        raise HTTPException(status_code=400, detail="Invalid role.")
    model = Server if role == "server" else Cashier

    existing_user = db.query(model).filter(model.email == email).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "This email is already registered."})

    try:
        validate_password_complexity(password)
    except HTTPException as e:
        return templates.TemplateResponse("register.html", {"request": request, "error": e.detail})

    hashed_pw = hash_password(password) # hashes pass
    user = model(name=name, email=email, password=hashed_pw, gender=gender, role=role) # saves
    db.add(user) # stores
    db.commit()

    if role == "server":
        history = PasswordHistory(server_id=user.id, hashed_password=hashed_pw) # server id becomes the user's id
    else:
        history = PasswordHistory(cashier_id=user.id, hashed_password=hashed_pw) # vice versa

    db.add(history)
    db.commit()
    return RedirectResponse("/login", status_code=303)

# login and dashboard
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    role = role.strip().lower() # normalize
    model = Server if role == "server" else Cashier
    user = db.query(model).filter(model.email == email).first()

    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid credentials."
        })

    # create token with email and role
    token = create_jwt_token({"sub": user.email, "role": role})
    # redirect to landing with token
    return templates.TemplateResponse("landing.html", {"request": request, "token": token})

# jwt part
# users login with email and pass
# if valid, token is generated and returned
# token contains sub (email) and role (cashier or server)
@app.post("/login-jwt")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Server).filter(Server.email == form_data.username).first()
    role = "server"
    if not user:
        user = db.query(Cashier).filter(Cashier.email == form_data.username).first()
        role = "cashier"
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect credentials")
    token = create_jwt_token({"sub": user.email, "role": role})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/login-jwt/server")
def login_server(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Server).filter(Server.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect email or password!")
    token = create_jwt_token({"sub": user.email, "role": "server"})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/login-jwt/cashier")
def login_cashier(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Cashier).filter(Cashier.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect email or password!")
    token = create_jwt_token({"sub": user.email, "role": "cashier"})
    return {"access_token": token, "token_type": "bearer"}

# dashboard after successful login
# validates jwt and returns server-page or cashier-dashboard
@app.post("/access-dashboard", response_class=HTMLResponse)
def access_dashboard(
    request: Request,
    token: str = Form(...),
    target: str = Form(...),  # "server" or "cashier"
    db: Session = Depends(get_db)
):
    # payload ghyaycha token decode karun
    payload = decode_jwt_token(token)
    if not payload:
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "error": "Invalid or expired token.",
            "token": token
        })

    # role and email fetch karaycha
    user_role = payload.get("role")
    email = payload.get("sub")

    # check if token is complete
    if not email or not user_role:
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "error": "Token missing required info.",
            "token": token
        })

    # check if role is allowed
    if user_role != target:
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "error": "Access forbidden for your role.",
            "token": token
        })

    # redirect to the appropriate dashboard with the token as a query parameter
    if user_role == "server":
        return RedirectResponse(f"/server-page?token={token}", status_code=303)
    elif user_role == "cashier":
        return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

# reset password
@app.post("/send-reset-link")
def send_reset_link(request: Request, email: str = Form(...), role: str = Form(...), db: Session = Depends(get_db)):
    model = Server if role == "server" else Cashier
    user = db.query(model).filter(model.email == email).first()
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Email not found."})
    token = URLSafeTimedSerializer(SECRET_KEY).dumps(email, salt=SECURITY_PASSWORD_SALT)
    link = f"http://127.0.0.1:8000/reset-password/{role}/{token}"
    msg = MIMEText(f"Reset your password: {link}")
    msg['Subject'] = 'Reset Password'
    msg['From'] = 'diyakalamkar2005@gmail.com'
    msg['To'] = email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login("diyakalamkar2005@gmail.com", "xgti tpuj prfh hgcq")
        server.send_message(msg)
    return templates.TemplateResponse("login.html", {"request": request, "message": "Password reset link sent."})

@app.get("/reset-password/{role}/{token}", response_class=HTMLResponse)
def reset_password_form(role: str, token: str, request: Request):
    return templates.TemplateResponse("reset.html", {"request": request, "token": token, "role": role})

@app.post("/reset-password/{role}/{token}")
def reset_password(role: str, token: str, request: Request, password: str = Form(...), db: Session = Depends(get_db)):
    model = Server if role == "server" else Cashier
    try:
        email = URLSafeTimedSerializer(SECRET_KEY).loads(token, salt=SECURITY_PASSWORD_SALT, max_age=3600) # 1 hour
    except:
        return templates.TemplateResponse("reset.html", {"request": request, "token": token, "role": role, "error": "Invalid or expired token."})
    user = db.query(model).filter(model.email == email).first()
    if not user:
        return templates.TemplateResponse("reset.html", {"request": request, "token": token, "role": role, "error": "User not found."})

    # check if the password meets the requirements
    try:
        validate_password_complexity(password)
    except HTTPException as e:
        return templates.TemplateResponse("reset.html", {"request": request, "token": token, "role": role, "error": e.detail})
    
    if role == "server":
        previous_passwords = db.query(PasswordHistory).filter(PasswordHistory.server_id == user.id).all() # server_id
    else:
        previous_passwords = db.query(PasswordHistory).filter(PasswordHistory.cashier_id == user.id).all() #cashier_id

    # check if it has been reused
    for old in previous_passwords:
        if bcrypt.checkpw(password.encode('utf-8'), old.hashed_password.encode('utf-8')):
            return templates.TemplateResponse("reset.html", {
                "request": request,
                "token": token,
                "role": role,
                "error": "Password reused. Choose a new one."
            })

    # hash the new password
    new_hashed = hash_password(password)
    user.password = new_hashed

    # store according to role
    if role == "server":
        history = PasswordHistory(server_id=user.id, hashed_password=new_hashed)
    else:
        history = PasswordHistory(cashier_id=user.id, hashed_password=new_hashed)
    
    db.add(history)
    db.commit()

    # send to login page
    return RedirectResponse("/login", status_code=303)

# cart creation and adding items
# create a cart for the current cashier
@app.post("/cart", response_model=CartResponse)
def create_cart(
    channel: str = Form(...), # dine-in or takeaway
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # check role
    if current_user.role != "cashier":
        raise HTTPException(403, "Only cashiers can create carts.")

    # check channel
    if channel not in ["Dine-In", "Takeaway"]:
        raise HTTPException(400, "Invalid channel.")
    print(f"Received channel: {channel}")

    # for already created carts
    existing_cart = db.query(Cart).filter_by(cashier_id=current_user.id, is_checked_out=False).first()
    if existing_cart:
        existing_cart.channel = channel  # update channel first
        db.commit() # then store
        db.refresh(existing_cart)
        return existing_cart

    cart = Cart(cashier_id=current_user.id, channel=channel)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart

# view the items in a cart
@app.get("/cart/{cart_id}/items", response_model=List[CartItemResponse])
def view_cart_items(cart_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "cashier":
        raise HTTPException(403, "Only cashiers can view their cart.")
    
    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=current_user.id).first()
    if not cart:
        raise HTTPException(404, "Cart not found.")
    
    return cart.items

@app.get("/cashier-dashboard", response_class=HTMLResponse)
async def cashier_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "cashier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access not allowed for your role!"
        )

    token_for_template = request.query_params.get("token")

    cart = db.query(Cart).options(
    joinedload(Cart.items),
    joinedload(Cart.deals)
        .joinedload(CartDeal.items)
        .joinedload(CartDealItem.modifiers)
    ).filter_by(cashier_id=user.id, is_checked_out=False).first()


    # Handle old cart cleanup if everything in it is voided
    if cart:
        active_items = db.query(CartItem).filter_by(cart_id=cart.id, is_voided=False).count()
        active_deals = db.query(CartDeal).filter_by(cart_id=cart.id, is_voided=False).count()
        if active_items == 0 and active_deals == 0:
            db.delete(cart)
            db.commit()
            cart = None

    # If no valid cart, create new one
    if not cart:
        channel_param = request.query_params.get("channel") or "Dine-In"
        cart = Cart(
            cashier_id=user.id,
            channel = cart.channel if cart else channel_param,
            receipt_number=f"TMP-{datetime.now(IST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        )
        db.add(cart)
        db.commit()
        db.refresh(cart)

    # Fetch all items (including voided, so they show up in UI with strikethrough)
    cart_items = db.query(CartItem).filter_by(cart_id=cart.id).all()

    products = db.query(Product).filter_by(active=True).all()
    discounts = db.query(Discount).filter_by(active=True).all()
    deals = db.query(Deal).filter_by(active=True).all()

    # Subtotal from unvoided items only
    subtotal = sum(item.quantity * item.price for item in cart_items if not item.is_voided)

    for deal in cart.deals:
        if deal.is_voided:
            continue
        for item in deal.items:
            if item.is_voided:
                continue
            print(f"{item.product_name} modifiers: {[m.modifier_name for m in item.modifiers]}")
            mod_total = sum(mod.price_diff for mod in item.modifiers)
            subtotal += item.quantity * (item.price + mod_total)

    cart.subtotal = round(subtotal, 2)
    cart.tax = round(cart.subtotal * 0.05, 2)
    cart.total = round(cart.subtotal + cart.tax - (cart.discount_amount or 0.0), 2)
    db.commit()

    # Product IDs (for modifier filtering)
    cart_product_ids = [
        db.query(Product.id).filter_by(name=item.product_name).scalar()
        for item in cart_items
    ]
    for deal in cart.deals:
        cart_product_ids += [item.product_id for item in deal.items]

    modifiers = db.query(Modifier).filter(
        or_(
            Modifier.for_product_id.in_(cart_product_ids),
            Modifier.for_product_id == None
        )
    ).all()

    return templates.TemplateResponse("cashier.html", {
        "request": request,
        "user": user,
        "token": token_for_template,
        "cart": cart,
        "cart_items": cart_items,
        "products": products,
        "discount_amount": cart.discount_amount or 0.0,
        "discounts": discounts,
        "deals": deals,
        "modifiers": modifiers,
        "subtotal": cart.subtotal,
        "tax": cart.tax,
        "total": cart.total,
    })

# server dashboard 
@app.get("/server-page", response_class=HTMLResponse)
def server_page(request: Request,
                db: Session = Depends(get_db),
                user=Depends(get_current_user) # authentication is handled here
                ):
    if user.role != "server":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: Not a server.")

    token_for_template = request.query_params.get("token")

    return templates.TemplateResponse("server.html", {
        "request": request,
        "user": user,
        "token": token_for_template, # pass the raw token string to the template for JS use
    })

# remove the redundant authentication logic from add_item_html as well
@app.post("/cart-html/{cart_id}/add-item", response_class=HTMLResponse)
def add_item_html(
    cart_id: int,
    product_id: int = Form(...),
    quantity: int = Form(...),
    token: str = Form(...),  # if you're passing token in form too
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user.role != "cashier":
        raise HTTPException(status_code=403, detail="Only cashiers can add items.")

    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=current_user.id, is_checked_out=False).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found or already checked out.")

    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    
    print(f"Received product_id: {product.id}, name: {product.name}, price: {product.price}")
    
    cart_item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        product_name=product.name,
        quantity=quantity,
        price=product.price
    )
    db.add(cart_item)

    subtotal = sum(i.quantity * i.price for i in cart.items if not i.is_voided)
    tax = round(subtotal * 0.05, 2)
    total = round(subtotal + tax, 2)

    cart.subtotal = subtotal
    cart.tax = tax
    cart.total = total

    db.commit()
    db.refresh(cart_item)

    # Redirect or render template if needed
    return RedirectResponse(url=f"/cashier-dashboard?token={token}", status_code=303)

# remove items individually
@app.post("/cart-html/{cart_id}/remove-item", response_class=HTMLResponse)
def remove_item_html(
    request: Request,
    cart_id: int,
    item_id: int = Form(...),
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if user.role != "cashier":
        return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    if not cart:
        return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

    item = db.query(CartItem).filter_by(id=item_id, cart_id=cart.id).first()
    if item:
        db.delete(item)
        db.commit()

        # recalculate totals
        subtotal = sum(i.quantity * i.price for i in cart.items)
        cart.subtotal = round(subtotal, 2)
        cart.tax = round(subtotal * 0.05, 2)
        cart.total = round(cart.subtotal + cart.tax, 2)
        db.commit()

    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

# cart deletion
@app.post("/cart-html/{cart_id}/delete-cart", response_class=HTMLResponse)
def delete_cart_html(
    request: Request,
    cart_id: int,
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    if cart:
        db.delete(cart) # remove it
        db.commit()
    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

# receipt for the cart
@app.get("/receipt/{cart_id}", response_class=HTMLResponse)
def view_receipt(cart_id: int, request: Request, token: str = Query(...),
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id).first()
    if not cart or not cart.is_checked_out:
        return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)
    return templates.TemplateResponse("receipt.html", {
        "request": request,
        "user": user,
        "cart": cart,
        "cart_items": cart.items,
        "token": token
    })

@app.post("/cart-html/{cart_id}/apply-discount", response_class=HTMLResponse)
def apply_discount(
    request: Request,
    cart_id: int,
    discount_id: Optional[int] = Form(None),
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    selected_discount = db.query(Discount).filter_by(id=discount_id, active=True).first() if discount_id else None

    subtotal = cart.subtotal or 0.0
    discount_amount = 0.0
    discount_not_applied = False
    discount_name = None
    min_order_value = None

    if selected_discount:
        discount_name = selected_discount.name
        min_order_value = selected_discount.min_order_value

        if subtotal >= selected_discount.min_order_value:
            if selected_discount.type == "amount":
                discount_amount = selected_discount.value

            elif selected_discount.type == "percentage":
                percent_discount = (selected_discount.value / 100.0) * subtotal
                discount_amount = min(percent_discount, selected_discount.max_discount or percent_discount)

            elif selected_discount.type == "item":
                product_name = selected_discount.product_name
                if product_name:
                    # Match CartItem by name
                    item_discount = sum(
                        item.quantity * selected_discount.value
                        for item in cart.items
                        if not item.is_voided and item.product_name == product_name
                    )

                    # Match Deal Items by name
                    deal_item_discount = 0
                    for deal in cart.deals:
                        if deal.is_voided:
                            continue
                        for d_item in deal.items:
                            if not d_item.is_voided and d_item.product_name == product_name:
                                deal_item_discount += d_item.quantity * selected_discount.value

                    discount_amount = item_discount + deal_item_discount
                else:
                    discount_amount = 0.0

            cart.discount_applied = selected_discount.name
        else:
            discount_not_applied = True
            cart.discount_applied = None

    cart.discount_amount = round(discount_amount, 2)
    cart.tax = round((cart.subtotal or 0.0) * 0.05, 2)
    cart.total = round((cart.subtotal or 0.0) + cart.tax - cart.discount_amount, 2)
    db.commit()

    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

@app.post("/cart-html/{cart_id}/checkout", response_class=HTMLResponse)
def checkout_cart(
    request: Request,
    cart_id: int,
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    payment_methods: List[str] = Form(...),
    amounts: List[float] = Form(...),
    tender_flags: Optional[List[str]] = Form(None),
):
    # cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    cart = db.query(Cart).options(
        joinedload(Cart.deals)
        .joinedload(CartDeal.deal)
    ).options(
        joinedload(Cart.deals)
        .joinedload(CartDeal.items)
        .joinedload(CartDealItem.modifiers)
    ).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    if not cart:
        return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

    # Normalize tender flags
    tender_flags_raw = tender_flags or []
    while len(tender_flags_raw) < len(payment_methods):
        tender_flags_raw.append("")
    tender_flags_bool = [(flag == "on") for flag in tender_flags_raw]

    # Recalculate totals
    subtotal = sum(i.quantity * i.price for i in cart.items if not i.is_voided)
    for deal in cart.deals:
        if deal.is_voided:
            continue
        for item in deal.items:
            if item.is_voided:
                continue
            modifier_total = sum(m.price_diff for m in item.modifiers)
            subtotal += item.quantity * (item.price + modifier_total)

    cart.subtotal = round(subtotal, 2)
    cart.tax = round(cart.subtotal * 0.05, 2)

    discount = cart.discount_amount or 0.0
    cart.total = round(cart.subtotal + cart.tax - discount, 2)

    expected_total = round(cart.total)
    total_paid = sum(amounts)

    # Allow cash overpay only if cash is marked as tendered
    tendered_cash = sum(
        amount for method, amount, tender in zip(payment_methods, amounts, tender_flags_bool)
        if method == "cash" and (tender or len(payment_methods) == 1)
    )

    # Allow overpayment only if it's from tendered cash
    if total_paid > expected_total:
        # Only cash tendered is allowed to overpay
        overpaid_amount = total_paid - expected_total

        if tendered_cash == 0 or overpaid_amount > (tendered_cash - (expected_total - cart.total_paid if cart.total_paid else 0)):
            return templates.TemplateResponse("cashier.html", {
                "request": request,
                "user": user,
                "token": token,
                "cart": cart,
                "cart_items": cart.items,
                "products": db.query(Product).filter_by(active=True).all(),
                "discount_amount": cart.discount_amount or 0.0,
                "discounts": db.query(Discount).filter_by(active=True).all(),
                "deals": db.query(Deal).filter_by(active=True).all(),
                "modifiers": db.query(Modifier).all(),
                "subtotal": cart.subtotal,
                "tax": cart.tax,
                "total": cart.total,
                "error": f"Overpayment of ₹{overpaid_amount:.2f} is not allowed. Please enter correct amount."
            })

    # Optional: You can also check underpayment and prevent it like this:
    if total_paid < expected_total:
        return templates.TemplateResponse("cashier.html", {
            "request": request,
            "user": user,
            "token": token,
            "cart": cart,
            "cart_items": cart.items,
            "products": db.query(Product).filter_by(active=True).all(),
            "discount_amount": cart.discount_amount or 0.0,
            "discounts": db.query(Discount).filter_by(active=True).all(),
            "deals": db.query(Deal).filter_by(active=True).all(),
            "modifiers": db.query(Modifier).all(),
            "subtotal": cart.subtotal,
            "tax": cart.tax,
            "total": cart.total,
            "error": f"Paid ₹{total_paid}, but total due is ₹{expected_total}."
        })

    # Update checkout flags
    cart.checked_out_at = datetime.now(IST)
    cart.is_checked_out = True
    cart.receipt_number = f"DMK-{datetime.now(IST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    # Save payments
    for method, amount, is_tender in zip(payment_methods, amounts, tender_flags_bool):
        db.add(Payment(
            cart_id=cart.id,
            method=method,
            amount=amount,
            is_tender=is_tender
        ))

    # Total paid
    total_paid = sum(amounts)
    cart.total_paid = total_paid
    cart.payment_method = ", ".join(payment_methods)

    # Cash-specific values
    
    # Total paid in cash regardless of tender checkbox
    cash_received = sum(
        amount for method, amount in zip(payment_methods, amounts) if method == "cash"
    )
    cart.cash_received = cash_received

    # Treat **any** cash as tendered if it's the **only** payment method
    tendered_cash = sum(
        amount for method, amount, tender in zip(payment_methods, amounts, tender_flags_bool)
        if method == "cash" and (tender or len(payment_methods) == 1)
    )

    cart.cash_received = cash_received

    if tendered_cash > 0:
        cart.rounded_total = round(cart.total)
        cart.round_off_amount = round(cart.rounded_total - cart.total, 2)
        cart.change_returned = round(tendered_cash + (total_paid - tendered_cash) - cart.rounded_total, 2)
    else:
        cart.rounded_total = None
        cart.round_off_amount = None
        cart.change_returned = None

    db.commit()
    return RedirectResponse(f"/receipt/{cart.id}?token={token}", status_code=303)

# deals and combos
# FastAPI endpoints for deals and meal modifiers
@app.get("/deals", response_class=HTMLResponse)
def list_deals(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    deals = db.query(Deal).filter(Deal.active == True).all()
    return {"deals": deals}

@app.post("/cart-html/{cart_id}/add-deal", response_class=HTMLResponse)
async def add_deal_to_cart(
    request: Request,
    cart_id: int,
    deal_id: int = Form(...),
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    form = await request.form()

    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    deal = db.query(Deal).filter_by(id=deal_id, active=True).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    cart_deal = CartDeal(
        cart_id=cart.id,
        deal_id=deal.id,
        deal_name=deal.name,
        total_price=0.0
    )
    db.add(cart_deal)
    db.flush()  # so cart_deal.id is ready

    total_deal_price = 0.0

    for index, deal_item in enumerate(deal.items):
        product_id = deal_item.product_id

        # Handle optional swap
        swap_key = f"swap_product_{index}"
        if swap_key in form:
            try:
                product_id = int(form[swap_key])
            except:
                pass

        product = db.query(Product).filter_by(id=product_id).first()
        if not product:
            continue

        cart_deal_item = CartDealItem(
            cart_deal_id=cart_deal.id,
            original_deal_item_id=deal_item.id,
            product_id=product.id,
            product_name=product.name,
            quantity=deal_item.quantity,
            price=product.price
        )
        db.add(cart_deal_item)
        db.flush()  # ensures cart_deal_item.id is available

        item_total = cart_deal_item.price * cart_deal_item.quantity

        # Handle modifier if selected
        modifier_key = f"modifier_{index}"
        if modifier_key in form:
            try:
                modifier_id = int(form[modifier_key])
                modifier = db.query(Modifier).filter_by(id=modifier_id).first()
                if modifier:
                    db.add(CartDealItemModifier(
                        cart_deal_item_id=cart_deal_item.id,
                        modifier_id=modifier.id,
                        modifier_name=modifier.name,
                        price_diff=modifier.price_diff
                    ))
                    item_total += deal_item.quantity * modifier.price_diff
                    #item_total += modifier.price_diff  # once per item, not per unit
                    cart_deal_item.price += modifier.price_diff
            except Exception as e:
                print("Modifier error:", e)

        total_deal_price += item_total

    # Save total deal price
    cart_deal.total_price = round(total_deal_price, 2)
    db.commit()

    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

# items to be swapped
@app.get("/cart/{cart_id}/deal-item/{deal_item_id}/swap-options")
def get_swap_options(cart_id: int, deal_item_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cart_deal_item = db.query(CartDealItem).filter_by(id=deal_item_id).first()
    if not cart_deal_item:
        raise HTTPException(status_code=404, detail="Deal item not found")

    deal = cart_deal_item.cart_deal.deal
    if not deal.editable:
        raise HTTPException(status_code=400, detail="This deal is not editable")

    # Fetch options (e.g., all products of same category, or by tag)
    # For now, let’s assume same category or dummy filter
    swap_options = db.query(Product).filter(Product.active == True).all()

    return {"swap_options": [{"id": p.id, "name": p.name, "price": p.price} for p in swap_options]}


@app.post("/cart/{cart_id}/deal-item/{deal_item_id}/swap")
def swap_deal_item(
    cart_id: int,
    deal_item_id: int,
    new_product_id: int = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cart_deal_item = db.query(CartDealItem).filter_by(id=deal_item_id).first()
    if not cart_deal_item:
        raise HTTPException(status_code=404, detail="Deal item not found")

    deal = cart_deal_item.cart_deal.deal
    if not deal.editable:
        raise HTTPException(status_code=400, detail="This deal does not support swapping")

    new_product = db.query(Product).filter_by(id=new_product_id, active=True).first()
    if not new_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Perform the swap
    cart_deal_item.product_id = new_product.id
    cart_deal_item.product_name = new_product.name
    cart_deal_item.price = new_product.price  # You can adjust logic for price difference
    db.commit()

    return {"message": f"{cart_deal_item.product_name} swapped successfully with {new_product.name}"}

@app.post("/cart-html/{cart_id}/remove-deal")
def remove_deal(cart_id: int, cart_deal_id: int = Form(...), token: str = Form(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    cart_deal = db.query(CartDeal).filter_by(id=cart_deal_id, cart_id=cart_id).first()
    if not cart_deal:
        raise HTTPException(status_code=404, detail="Deal not found in cart")

    db.delete(cart_deal)
    db.commit()
    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

@app.post("/cart-html/{cart_id}/deal-item/{item_id}/edit-modifiers", response_class=HTMLResponse)
async def edit_cart_deal_item_modifier(
    request: Request,
    cart_id: int,
    item_id: int,
    modifier_id: int = Form(...),
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    cart_deal_item = db.query(CartDealItem).filter_by(id=item_id).first()
    if not cart_deal_item:
        raise HTTPException(status_code=404, detail="Cart deal item not found")

    # Remove previous modifiers
    db.query(CartDealItemModifier).filter_by(cart_deal_item_id=cart_deal_item.id).delete()
    db.commit()

    # Get product base price
    product = db.query(Product).filter_by(id=cart_deal_item.product_id).first()
    base_price = product.price if product else 0.0
    modifier_price = 0.0

    # Add new modifier if exists
    modifier = db.query(Modifier).filter_by(id=modifier_id).first()
    if modifier:
        mod_entry = CartDealItemModifier(
            cart_deal_item_id=cart_deal_item.id,
            modifier_id=modifier.id,
            modifier_name=modifier.name,
            price_diff=modifier.price_diff
        )
        db.add(mod_entry)
        modifier_price += modifier.price_diff

    # Update item price
    cart_deal_item.price = base_price + modifier_price
    db.commit()

    # Recalculate deal price
    cart_deal = db.query(CartDeal).filter_by(id=cart_deal_item.cart_deal_id).first()
    if cart_deal:
        cart_deal.total_price = sum(item.price * item.quantity for item in cart_deal.items)
        db.commit()

    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

# Fetch line items for a deal with proper modifiers per item
@app.get("/api/deals/{deal_id}/line-items")
def get_deal_line_items(
    deal_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    deal = db.query(Deal).filter_by(id=deal_id, active=True).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    items_data = []

    for deal_item in deal.items:
        product = db.query(Product).filter_by(id=deal_item.product_id).first()
        if not product:
            continue

        # Fetch only modifiers specific to this product
        modifiers = db.query(Modifier).filter(Modifier.for_product_id == product.id).all()

        items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "editable": deal.editable and not deal_item.required,  # only if not required
            "required": deal_item.required,
            "quantity": deal_item.quantity,
            "modifiers": [
                {
                    "id": m.id,
                    "name": m.name,
                    "extra_price": m.price_diff,
                    "for_product_id": m.for_product_id
                } for m in modifiers
            ]
        })

    all_products = db.query(Product).filter(Product.active == True).all()

    return {
        "items": items_data,
        "all_products": [{"id": p.id, "name": p.name} for p in all_products]
    }

@app.post("/cart-html/{cart_id}/deal-item/{deal_item_id}/swap", response_class=HTMLResponse)
def swap_deal_item(
    cart_id: int,
    deal_item_id: int,
    new_product_id: int = Form(...),
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    cart = db.query(Cart).filter_by(id=cart_id, cashier_id=user.id, is_checked_out=False).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    deal_item = db.query(CartDealItem).filter_by(id=deal_item_id).first()
    if not deal_item:
        raise HTTPException(status_code=404, detail="Deal item not found")

    if not deal_item.cart_deal.deal.editable:
        raise HTTPException(status_code=403, detail="This deal is not editable")

    # Ensure original deal item exists and is not required
    original = db.query(DealItem).filter_by(id=deal_item.original_deal_item_id).first()
    if not original or original.required:
        raise HTTPException(status_code=403, detail="This item cannot be swapped")


    product = db.query(Product).filter_by(id=new_product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    deal_item.product_id = product.id
    deal_item.product_name = product.name
    deal_item.price = product.price
    db.commit()

    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

#voiding entries
@app.post("/cart-html/{cart_id}/void-item", response_class=HTMLResponse)
def void_item(cart_id: int, item_id: int = Form(...), token: str = Form(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = db.query(CartItem).filter_by(id=item_id, cart_id=cart_id).first()
    if item:
        item.is_voided = True
        db.commit()
        db.refresh(item)  # <--- this line ensures data is refreshed
    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)

#voiding deals
@app.post("/cart-html/{cart_id}/void-deal", response_class=HTMLResponse)
def void_deal(
    cart_id: int,
    cart_deal_id: int = Form(...),
    token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    deal = db.query(CartDeal).filter_by(id=cart_deal_id, cart_id=cart_id).first()
    if deal:
        print("Voiding cart_deal_id:", cart_deal_id)
        print("Before void:", deal.is_voided)
        deal.is_voided = True
        db.add(deal)
        db.commit()
        db.refresh(deal)  # Already doing this, good
        print("After void:", deal.is_voided)
        print("Final DB value:", db.query(CartDeal).filter_by(id=cart_deal_id).first().is_voided)

    return RedirectResponse(f"/cashier-dashboard?token={token}", status_code=303)





