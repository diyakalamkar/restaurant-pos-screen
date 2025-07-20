-- Size modifiers for all pizza products (IDs 1 to 19)
INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT '8 Inches', 0, id FROM products WHERE id BETWEEN 1 AND 19;

INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT '10 Inches', 50, id FROM products WHERE id BETWEEN 1 AND 19;

INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT '12 Inches', 100, id FROM products WHERE id BETWEEN 1 AND 19;

-- Default modifier for Garlic Breads
INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT 'Regular', 0, id FROM products WHERE id BETWEEN 20 AND 24;

-- Default modifier for Drinks
INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT '500ml Regular', 0, id FROM products WHERE id BETWEEN 32 AND 37;

-- Add "Extra Cheese" and "Extra Spicy" to all Garlic Breads (IDs 20 to 24)
INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT 'Extra Cheese', 50, id FROM products WHERE id BETWEEN 20 AND 24;

INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT 'Extra Spicy', 30, id FROM products WHERE id BETWEEN 20 AND 24;

-- Add "750ml" and "1000ml" as modifiers to all Drinks (IDs 32 to 37)
INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT '750ml', 20, id FROM products WHERE id BETWEEN 32 AND 37;

INSERT INTO modifiers (name, price_diff, for_product_id)
SELECT '1000ml', 50, id FROM products WHERE id BETWEEN 32 AND 37;




