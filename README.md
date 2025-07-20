A fully-featured restaurant/retail POS (Point of Sale) system built using FastAPI.

1. **Authentication & Authorization:**
   - JWT-based login system  
   - Role-based access control (e.g., cashier, server)

2. **Cart & Order Management:**
   - Dynamic cart creation per user/session  
   - Add/remove items, update quantities  
   - Support for modifiers (e.g., sizes, extras)

3. **Deals & Discounts:**
   - Item-specific and cart-wide discounts  
   - Amount-based, percentage-based (with caps), and fixed deals  
   - Supports static and editable meal combos with swapping logic

4. **Payments:**
   - Multi-mode payment support (cash, UPI, card, split payments)  
   - Tender flags, rounding, and change calculation

5. **Frontend/UI:**
   - HTML rendered with Jinja2 templates  
   - Modern styling with custom CSS  
   - Responsive and intuitive layout

6. **Backend Technologies:**
   - Pydantic for data validation  
   - SQLAlchemy ORM for database operations  
   - Clean project structure with reusable utilities

---

Ideal for learning or adapting to production-ready POS applications in food/retail sectors.
