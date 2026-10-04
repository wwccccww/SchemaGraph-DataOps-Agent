CREATE TABLE t_user_level (
    level_id INT PRIMARY KEY,
    level_name VARCHAR(32) NOT NULL,
    discount_rate DECIMAL(3, 2) DEFAULT 1.00
);
COMMENT ON TABLE t_user_level IS '会员等级维表';
COMMENT ON COLUMN t_user_level.level_id IS '会员等级主键ID';
COMMENT ON COLUMN t_user_level.level_name IS 'VIP等级名称，如VIP1, VIP3';
COMMENT ON COLUMN t_user_level.discount_rate IS '等级基础折扣率';

CREATE TABLE t_region (
    region_id INT PRIMARY KEY,
    region_name VARCHAR(64) NOT NULL,
    province_name VARCHAR(64) NOT NULL
);
COMMENT ON TABLE t_region IS '基础行政区域维表';
COMMENT ON COLUMN t_region.region_id IS '区域唯一ID';
COMMENT ON COLUMN t_region.region_name IS '大区名称，如华东, 华南';
COMMENT ON COLUMN t_region.province_name IS '省份名称';

CREATE TABLE t_user (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    user_level_id INT NOT NULL REFERENCES t_user_level(level_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_user IS '用户基础账户表';
COMMENT ON COLUMN t_user.user_id IS '用户唯一ID';
COMMENT ON COLUMN t_user.username IS '用户注册用户名';
COMMENT ON COLUMN t_user.user_level_id IS '关联会员等级ID';
COMMENT ON COLUMN t_user.created_at IS '用户账号注册时间';

CREATE TABLE t_user_region_map (
    map_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES t_user(user_id),
    region_id INT NOT NULL REFERENCES t_region(region_id),
    address_detail VARCHAR(255) NOT NULL
);
COMMENT ON TABLE t_user_region_map IS '用户地址与区域映射表[Junction Table]';
COMMENT ON COLUMN t_user_region_map.map_id IS '映射记录主键ID';
COMMENT ON COLUMN t_user_region_map.user_id IS '关联用户ID';
COMMENT ON COLUMN t_user_region_map.region_id IS '关联区域ID';
COMMENT ON COLUMN t_user_region_map.address_detail IS '详细地址门牌文本';

CREATE TABLE t_merchant (
    merchant_id BIGINT PRIMARY KEY,
    merchant_name VARCHAR(128) NOT NULL,
    is_self_operated BOOLEAN DEFAULT FALSE
);
COMMENT ON TABLE t_merchant IS '入驻商家维度表';
COMMENT ON COLUMN t_merchant.merchant_id IS '商家唯一ID';
COMMENT ON COLUMN t_merchant.merchant_name IS '商家店铺全称';
COMMENT ON COLUMN t_merchant.is_self_operated IS '是否为平台自营商家';

CREATE TABLE t_category (
    category_id INT PRIMARY KEY,
    category_name VARCHAR(64) NOT NULL,
    parent_id INT DEFAULT 0
);
COMMENT ON TABLE t_category IS '商品类目树维表';
COMMENT ON COLUMN t_category.category_id IS '品类唯一ID';
COMMENT ON COLUMN t_category.category_name IS '品类名称，如美妆、数码';
COMMENT ON COLUMN t_category.parent_id IS '父级品类ID，0表示根节点';

CREATE TABLE t_product (
    product_id BIGINT PRIMARY KEY,
    product_name VARCHAR(128) NOT NULL,
    category_id INT NOT NULL REFERENCES t_category(category_id),
    merchant_id BIGINT NOT NULL REFERENCES t_merchant(merchant_id),
    price DECIMAL(10, 2) NOT NULL
);
COMMENT ON TABLE t_product IS '商品SPU主表';
COMMENT ON COLUMN t_product.product_id IS '商品唯一ID';
COMMENT ON COLUMN t_product.product_name IS '商品标准名称';
COMMENT ON COLUMN t_product.category_id IS '所属品类ID';
COMMENT ON COLUMN t_product.merchant_id IS '归属商家ID';
COMMENT ON COLUMN t_product.price IS '商品售卖单价';

CREATE TABLE t_coupon (
    coupon_id BIGINT PRIMARY KEY,
    coupon_name VARCHAR(64) NOT NULL,
    coupon_type VARCHAR(32) NOT NULL,
    min_amount DECIMAL(10, 2) DEFAULT 0.00
);
COMMENT ON TABLE t_coupon IS '营销优惠券主表';
COMMENT ON COLUMN t_coupon.coupon_id IS '优惠券唯一ID';
COMMENT ON COLUMN t_coupon.coupon_name IS '优惠券活动名称';
COMMENT ON COLUMN t_coupon.coupon_type IS '优惠券类型，如full_reduction或discount';
COMMENT ON COLUMN t_coupon.min_amount IS '门槛使用金额';

CREATE TABLE t_order (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES t_user(user_id),
    total_amount DECIMAL(10, 2) NOT NULL,
    order_status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE t_order IS '交易订单主事实表';
COMMENT ON COLUMN t_order.order_id IS '订单流水号主键';
COMMENT ON COLUMN t_order.user_id IS '下单用户ID';
COMMENT ON COLUMN t_order.total_amount IS '订单最终实付金额';
COMMENT ON COLUMN t_order.order_status IS '订单状态，如PAID、CANCELLED';
COMMENT ON COLUMN t_order.created_at IS '下单时间戳';

CREATE TABLE t_order_coupon_rel (
    rel_id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES t_order(order_id),
    coupon_id BIGINT NOT NULL REFERENCES t_coupon(coupon_id),
    discount_amount DECIMAL(10, 2) NOT NULL
);
COMMENT ON TABLE t_order_coupon_rel IS '订单与优惠券映射表[Junction Table]';
COMMENT ON COLUMN t_order_coupon_rel.rel_id IS '关联主键ID';
COMMENT ON COLUMN t_order_coupon_rel.order_id IS '关联订单ID';
COMMENT ON COLUMN t_order_coupon_rel.coupon_id IS '关联优惠券ID';
COMMENT ON COLUMN t_order_coupon_rel.discount_amount IS '该优惠券在此订单上的抵扣金额';

CREATE TABLE t_order_detail (
    detail_id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES t_order(order_id),
    product_id BIGINT NOT NULL REFERENCES t_product(product_id),
    quantity INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);
COMMENT ON TABLE t_order_detail IS '订单商品明细事实表';
COMMENT ON COLUMN t_order_detail.detail_id IS '明细主键ID';
COMMENT ON COLUMN t_order_detail.order_id IS '归属订单ID';
COMMENT ON COLUMN t_order_detail.product_id IS '购买商品ID';
COMMENT ON COLUMN t_order_detail.quantity IS '购买数量';
COMMENT ON COLUMN t_order_detail.price IS '购买时商品快照单价';

CREATE TABLE t_promo_sku_rel (
    rel_id BIGINT PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES t_product(product_id),
    coupon_id BIGINT NOT NULL REFERENCES t_coupon(coupon_id)
);
COMMENT ON TABLE t_promo_sku_rel IS '促销活动商品关联表[Junction Table]';
COMMENT ON COLUMN t_promo_sku_rel.rel_id IS '关联主键ID';
COMMENT ON COLUMN t_promo_sku_rel.product_id IS '促销适用商品ID';
COMMENT ON COLUMN t_promo_sku_rel.coupon_id IS '促销适用优惠券ID';

CREATE INDEX idx_user_level ON t_user(user_level_id);
CREATE INDEX idx_user_region_user ON t_user_region_map(user_id);
CREATE INDEX idx_user_region_region ON t_user_region_map(region_id);
CREATE INDEX idx_order_user ON t_order(user_id);
CREATE INDEX idx_order_created_at ON t_order(created_at);
CREATE INDEX idx_order_status ON t_order(order_status);
CREATE INDEX idx_order_coupon_order ON t_order_coupon_rel(order_id);
CREATE INDEX idx_order_coupon_coupon ON t_order_coupon_rel(coupon_id);
CREATE INDEX idx_order_detail_order ON t_order_detail(order_id);
CREATE INDEX idx_order_detail_product ON t_order_detail(product_id);
CREATE INDEX idx_product_category ON t_product(category_id);
CREATE INDEX idx_product_merchant ON t_product(merchant_id);
