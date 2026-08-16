CREATE TABLE dbo.customers (
    customer_unique_id  CHAR(32)     NOT NULL PRIMARY KEY,
    customer_zip_prefix CHAR(5)      NOT NULL,
    customer_city       NVARCHAR(64) NOT NULL,
    customer_state      CHAR(2)      NOT NULL,
    created_at          DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at          DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE dbo.products (
    product_id            CHAR(32)     NOT NULL PRIMARY KEY,
    product_category_name NVARCHAR(64) NULL,
    product_weight_g      INT          NULL,
    product_length_cm     INT          NULL,
    product_height_cm     INT          NULL,
    product_width_cm      INT          NULL,
    created_at            DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at            DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE dbo.sellers (
    seller_id         CHAR(32)     NOT NULL PRIMARY KEY,
    seller_zip_prefix CHAR(5)      NOT NULL,
    seller_city       NVARCHAR(64) NOT NULL,
    seller_state      CHAR(2)      NOT NULL,
    created_at        DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at        DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE dbo.orders (
    order_id                      CHAR(32)     NOT NULL PRIMARY KEY,
    customer_unique_id            CHAR(32)     NOT NULL,
    order_status                  VARCHAR(16)  NOT NULL,
    order_purchase_timestamp      DATETIME2(3) NOT NULL,
    order_approved_at             DATETIME2(3) NULL,
    order_delivered_carrier_date  DATETIME2(3) NULL,
    order_delivered_customer_date DATETIME2(3) NULL,
    order_estimated_delivery_date DATETIME2(3) NULL,
    updated_at                    DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_unique_id)
        REFERENCES dbo.customers(customer_unique_id)
);

CREATE TABLE dbo.order_items (
    order_id            CHAR(32)     NOT NULL,
    order_item_id       SMALLINT     NOT NULL,
    product_id          CHAR(32)     NOT NULL,
    seller_id           CHAR(32)     NOT NULL,
    shipping_limit_date DATETIME2(3) NULL,
    price               DECIMAL(10,2) NOT NULL,
    freight_value       DECIMAL(10,2) NOT NULL,
    updated_at          DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT pk_order_items PRIMARY KEY (order_id, order_item_id),
    CONSTRAINT fk_items_order   FOREIGN KEY (order_id)   REFERENCES dbo.orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES dbo.products(product_id),
    CONSTRAINT fk_items_seller  FOREIGN KEY (seller_id)  REFERENCES dbo.sellers(seller_id)
);

CREATE TABLE dbo.cdc_watermark (
    table_name        VARCHAR(64)  NOT NULL PRIMARY KEY,
    last_sync_version BIGINT       NOT NULL,
    last_sync_at      DATETIME2(3) NULL,
    rows_last_batch   INT          NULL
);

INSERT INTO dbo.cdc_watermark (table_name, last_sync_version)
VALUES ('orders', <seed>), ('order_items', <seed>), ('customers', <seed>);

/*
CREATE OR ALTER PROCEDURE dbo.sp_update_watermark
    @table_name VARCHAR(64), @new_version BIGINT, @rows INT
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE dbo.cdc_watermark
       SET last_sync_version = @new_version,
           last_sync_at = SYSUTCDATETIME(),
           rows_last_batch = @rows
     WHERE table_name = @table_name;
END
*/