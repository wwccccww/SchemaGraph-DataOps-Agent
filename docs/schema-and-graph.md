# Schema 与图拓扑设计

## 1. 设计目的

自建 Benchmark 使用电商交易中台主题域，包含 12 张表：

- 9 张实体、维度或事实表；
- 3 张无语义中间映射表；
- 3 条典型业务路径：用户区域、订单优惠券、商品促销。

向量检索只负责召回有业务语义的实体表。中间映射表必须由 Schema Graph 根据外键拓扑补全，以隔离向量语义泄漏。

## 2. 数据字典

| 表 | 类型 | 主要职责 |
| --- | --- | --- |
| `t_user_level` | 维度 | 会员等级 |
| `t_region` | 维度 | 大区和省份 |
| `t_user` | 实体 | 用户账户 |
| `t_user_region_map` | Junction | 用户与区域映射 |
| `t_merchant` | 维度 | 商家 |
| `t_category` | 维度 | 商品类目 |
| `t_product` | 实体 | 商品 |
| `t_coupon` | 实体 | 优惠券 |
| `t_order` | 事实 | 订单及最终实付金额 |
| `t_order_coupon_rel` | Junction | 订单使用的优惠券 |
| `t_order_detail` | 事实 | 订单商品明细 |
| `t_promo_sku_rel` | Junction | 优惠券适用商品 |

Junction Table 通过表注释中的 `[Junction Table]` 标记识别。索引构建器可以保存其原始元数据，但必须设置 `is_junction=true`，禁止进入 Seed Top-K。

## 3. 外键拓扑

```text
t_user_level ── t_user ── t_user_region_map ── t_region
                    │
                 t_order ── t_order_coupon_rel ── t_coupon
                    │                                  │
             t_order_detail                       t_promo_sku_rel
                    │                                  │
                t_product ─────────────────────────────┘
                  │    │
          t_category  t_merchant
```

图使用无向边进行路径搜索，但保留原始外键方向、约束名称和 Join 列，供 Prompt 构造和 SQL 生成使用。

## 4. 基准 DDL

```sql
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
```

## 5. Schema-RAG

实体表的向量文本由以下内容组成：

```text
表名 + 表中文注释 + 列名 + 列中文注释
```

Embedding 使用 `BAAI/bge-m3`，默认召回 Top-3～5。向量记录至少保存：

- `database_id`
- `schema_name`
- `table_name`
- `is_junction`
- `embedding_model`
- `embedding_version`
- `content_hash`

Junction Table 不参与 Seed Top-K 排名。禁止仅通过从结果中后置过滤 Junction Table 来虚增 Top-K；检索器应在候选查询阶段应用 `is_junction=false`。

## 6. Schema Graph 构建

### 6.1 显式边

优先从 PostgreSQL Catalog 或 DDL 中提取外键。每条边保存：

```text
source_table
source_columns
target_table
target_columns
constraint_name
weight = 1.0
inferred = false
```

### 6.2 隐式边

只有在缺乏显式外键时才启用隐式推断。候选列必须满足：

- 规范化列名相同，例如 `order_id`；
- 两端数据类型兼容；
- 至少一端是主键或唯一键；
- 采样数据的包含关系达到配置阈值；
- 不覆盖已有显式关系。

隐式边必须标记 `inferred=true` 和置信度。低置信度边不能进入自动路径，只能作为诊断信息。

## 7. 图扩展算法

### 7.1 第一阶段：1-Hop-per-Seed Junction 优先

对任意种子表对 `(vi, vj)`：

1. 计算邻居交集 `N(vi) ∩ N(vj)`；
2. 只选择 `is_junction=true` 的公共邻居；
3. 将桥接表及两条 Join 边加入子图。

该阶段解决：

```text
实体 A → 无语义映射表 → 实体 B
```

这里的 1-Hop 指 Junction 距每个 Seed 各 1 hop，两个实体之间的完整路径是 2 edges；实现中不能误设为总路径长度 1。

### 7.2 第二阶段：受限最短路径兜底

若种子表仍不在同一连通分量：

1. 在不同连通分量之间计算候选最短路径；
2. 丢弃长度超过 4 条边的路径；
3. 按“新增节点数、Junction 优先级、路径总权重、稳定字典序”排序；
4. 逐条加入新增成本最低的路径；
5. 直到种子表连通或预算耗尽。

约束：

```text
max_path_edges = 4
max_total_tables = 12
max_schema_tokens = 3500
```

路径节点具有原子性：不能为了 token 预算删除路径中的单个中间节点。预算不足时，优先降低 Seed Top-K 或舍弃低排名的整个候选分支，并在结果中返回 `context_truncated=true`。

### 7.3 失败语义

以下情况不得静默生成不完整 SQL：

- 种子节点之间不存在路径；
- 所有路径都超过最大深度；
- 必需路径加入后超过表数量或 token 预算；
- 路径只依赖低置信度隐式边。

系统应返回结构化图诊断，允许 Agent 请求补充元数据或明确报告上下文不足。

## 8. 造数不变量

固定锚点日期为 `2026-10-01`，固定随机种子建议为 `20261001`。默认规模：

| 实体 | 数量 |
| --- | ---: |
| 用户 | 20,000 |
| 区域 | 6 个大区及其省份 |
| 商家 | 200 |
| 品类 | 50 |
| 商品 | 10,000 |
| 优惠券 | 100 |
| 订单 | 120,000 |
| 订单明细 | 约 300,000 |

生成器必须保证：

- 同一订单的所有商品属于同一商家和同一末级品类；
- `t_order.total_amount` 是扣除优惠后的最终实付金额；
- 抵扣金额不大于商品毛额；
- `PAID` 订单才参与实付统计；
- 复杂评测条件组合具有非空且可区分的结果；
- 造数结束后显式执行 `ANALYZE`。

## 9. 11 表 Gold SQL 的角色

11 表 Gold SQL 是复杂 Benchmark 的标准参考答案，不是生产 Prompt 的一部分。它用于：

- 生成标准结果集；
- 验证 Schema Graph 是否补齐三个主题域路径；
- 计算 Execution Accuracy；
- 检查一对多 Join 后的重复聚合。

Gold SQL 必须先按 `order_id` 去重，再汇总最终实付金额。Agent 在评测时只能看到自然语言问题和允许的 Schema/工具上下文，不能读取 Gold SQL。
