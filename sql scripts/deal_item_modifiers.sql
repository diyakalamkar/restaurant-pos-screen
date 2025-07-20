-- Attach all modifiers of each pizza product to its matching deal_item
INSERT INTO deal_item_modifiers (deal_item_id, modifier_id)
SELECT di.id, m.id
FROM deal_items di
JOIN modifiers m ON di.product_id = m.for_product_id;
