INSERT INTO discounts 
(name, type, value, min_order_value, max_discount, product_name, active, product_id)
VALUES 
('FLAT 40% OFF upto Rs.200', 'percentage', 40, 1000, 200, NULL, 1, NULL); -- percentage-based

INSERT INTO discounts 
(name, type, value, min_order_value, max_discount, product_name, active, product_id)
VALUES 
('Rs.300 OFF Above Rs.2000', 'amount', 300, 2000, NULL, NULL, 1, NULL); -- amount-based

INSERT INTO discounts 
(name, type, value, min_order_value, max_discount, product_name, active, product_id)
VALUES 
('Rs.20 OFF on Sprite', 'item', 20, 300, 20, 'Sprite 500ml', 1, 32); -- item-based
-- 32 is the id of sprite in my products table




