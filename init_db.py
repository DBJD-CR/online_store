"""
数据库初始化脚本 (init_db.py)
用于创建商城系统所需的 SQLite 数据库结构，并填充初始的商品、评价及管理员激活码数据。
符合高抽象度和高覆盖率注释规范（注释率约 35%）。
"""

import sqlite3
import os

# 定义数据库文件的物理存储路径
DB_PATH = 'database.db'

def init_db():
    """
    初始化 SQLite 数据库的主函数。
    负责检测并清理旧数据库文件，新建所需的表结构并导入种子数据。
    """
    # 如果数据库文件已存在，则删除，以便重新初始化，确保开发调试环境干净
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("已检测到旧数据库，已清理。")

    # 建立与 SQLite 数据库的物理连接并创建游标对象以执行 SQL 命令
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 用户表 (新增 role 字段标记用户权限，'admin' 为管理员/商家，'user' 为普通买家用户)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 用户唯一自增 ID
        username TEXT UNIQUE NOT NULL,          -- 唯一用户名，用于登录凭证
        password TEXT NOT NULL,                 -- 登录密码，以明文或哈希方式存储
        role TEXT NOT NULL DEFAULT 'user'       -- 权限角色标识：'admin' / 'user'
    )
    ''')

    # 1.5 邀请码/激活码表 (用于注册时激活商家/管理员权限，保证系统权限安全性)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 自增主键 ID
        code TEXT UNIQUE NOT NULL,              -- 唯一的邀请激活码串
        is_used INTEGER NOT NULL DEFAULT 0      -- 激活码使用状态：0 未使用，1 已使用
    )
    ''')

    # 2. 收货地址表 (关联用户表，支持多收货地址管理)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 地址唯一自增 ID
        user_id INTEGER NOT NULL,               -- 关联的用户 ID
        name TEXT NOT NULL,                     -- 收货人姓名
        phone TEXT NOT NULL,                    -- 收货人联系电话
        province TEXT NOT NULL,                 -- 省份
        city TEXT NOT NULL,                     -- 城市
        district TEXT NOT NULL,                 -- 区县
        detail TEXT NOT NULL,                   -- 详细收货地址描述
        FOREIGN KEY (user_id) REFERENCES users (id) -- 外键约束：关联用户表
    )
    ''')

    # 3. 商品表 (存储商城售卖/展示的所有商品)
    # is_real: 1 表示真实可售，0 表示虚拟展示（障眼法商品）
    # status: 'active' (正常销售), 'soldout' (已售罄), 'preview' (下期预告)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 商品唯一自增 ID
        name TEXT NOT NULL,                     -- 商品名称
        price REAL NOT NULL,                    -- 商品基础标价（对应默认/大号规格）
        stock INTEGER NOT NULL,                 -- 当前可用库存量
        description TEXT,                       -- 商品详细介绍与功能描述
        image TEXT,                             -- 商品主图的相对 URL 路径
        is_real INTEGER NOT NULL DEFAULT 1,     -- 是否为真实商品：1 真实，0 虚拟
        status TEXT NOT NULL DEFAULT 'active'   -- 商品状态：active / soldout / preview
    )
    ''')

    # 4. 购物车表 (记录用户添加但尚未下单的商品明细)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 购物车条目唯一自增 ID
        user_id INTEGER NOT NULL,               -- 关联的用户 ID
        product_id INTEGER NOT NULL,            -- 关联的商品 ID
        quantity INTEGER NOT NULL DEFAULT 1,    -- 加入购物车的目标数量
        sku_color TEXT,                         -- 商品 SKU 颜色属性
        sku_size TEXT,                          -- 商品 SKU 尺寸属性（如大号、小号）
        FOREIGN KEY (user_id) REFERENCES users (id),       -- 外键约束：关联用户表
        FOREIGN KEY (product_id) REFERENCES products (id)  -- 外键约束：关联商品表
    )
    ''')

    # 5. 订单表 (存储买家支付、发货等核心交易记录)
    # status: 'pending_pay' (待付款), 'pending_ship' (待发货), 'pending_recv' (待收货), 'completed' (已完成)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 订单唯一自增 ID
        order_no TEXT UNIQUE NOT NULL,          -- 唯一订单号（时间戳 + 随机数）
        user_id INTEGER NOT NULL,               -- 下单用户 ID
        address_name TEXT NOT NULL,             -- 订单快照：收货人姓名
        address_phone TEXT NOT NULL,            -- 订单快照：收货人电话
        address_detail TEXT NOT NULL,           -- 订单快照：收货人详细地址
        total_amount REAL NOT NULL,             -- 订单实付/应付总金额
        payment_method TEXT NOT NULL,           -- 支付方式：alipay (支付宝) / wechat (微信) / cod (货到付款)
        status TEXT NOT NULL DEFAULT 'pending_pay', -- 订单交易状态
        tracking_no TEXT,                       -- 快递/运单单号
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 订单创建时间
        FOREIGN KEY (user_id) REFERENCES users (id) -- 外键约束：关联用户表
    )
    ''')

    # 6. 订单明细表 (用于记录订单生成瞬间的商品快照数据)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 明细唯一自增 ID
        order_id INTEGER NOT NULL,              -- 关联的订单主表 ID
        product_id INTEGER NOT NULL,            -- 关联的商品 ID
        product_name TEXT NOT NULL,             -- 购买时商品名称快照
        price REAL NOT NULL,                    -- 购买时商品实际单价快照
        quantity INTEGER NOT NULL,              -- 购买的数量
        sku_color TEXT,                         -- 商品颜色快照
        sku_size TEXT,                          -- 商品尺寸快照
        FOREIGN KEY (order_id) REFERENCES orders (id),     -- 外键约束：关联订单表
        FOREIGN KEY (product_id) REFERENCES products (id)  -- 外键约束：关联商品表
    )
    ''')

    # 7. 用户评价表 (记录用户对购买商品的打分与主观评论)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 评价唯一自增 ID
        product_id INTEGER NOT NULL,            -- 评价的目标商品 ID
        username TEXT NOT NULL,                 -- 评价人的用户名
        content TEXT NOT NULL,                  -- 评价文本内容
        rating INTEGER NOT NULL DEFAULT 5,      -- 星级评分（1 - 5 星）
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 评价发表时间
        FOREIGN KEY (product_id) REFERENCES products (id) -- 外键约束：关联商品表
    )
    ''')

    # 插入初始商品数据（包含2个真实销售商品及4个用于界面美观排版的虚拟商品）
    # 按照具体业务价格设定：
    # 盒子：大号 12.90 元，小号 9.90 元
    # 袋子：大号 7.70 元，小号 5.50 元
    products_data = [
        # 2个真实商品
        (
            "鲜时家 日期记忆保鲜盒",
            12.9,
            99,
            "【热销推荐】日期记忆保鲜盒，顶盖带手动拨盘记录日期，拒绝食物过期！密封防渗漏，防串味，食品级PP材质安全耐用。大号适合装蔬菜瓜果，小号适合装便当配菜，冰箱叠放易收纳，守护每日新鲜！",
            "/static/images/box1.png",
            1,
            "active"
        ),
        (
            "鲜时家 日期记忆保鲜袋",
            7.7,
            150,
            "【加厚耐用】日期记忆保鲜袋，袋身自带可手写/标记日期区域，轻松记录保鲜期。采用食品级PE材质，双拉链双重密封，防潮防串味，大号适合封存整鸡整鱼，小号适合备餐收纳，是您厨房的保鲜好帮手。",
            "/static/images/bag1.jpg",
            1,
            "active"
        ),
        # 4个虚拟障眼法商品（补足一倍）
        (
            "鲜时家 智能真空封口机（已售罄）",
            199.0,
            0,
            "【下期热卖】全自动真空保鲜封口机，强劲大吸力，一键干湿通用，持久锁鲜。配置精细封口调节，附带真空管，完美适配保鲜罐。",
            "/static/images/vacuum_machine.jpg",
            0,
            "soldout"
        ),
        (
            "鲜时家 多功能食品密封夹（预售中）",
            9.9,
            0,
            "【新春限定】糖果色防潮密封夹，出料嘴设计，倒取方便，咬合力强，轻松夹住各类零食袋，防潮防霉防虫蛀，小身材大用途。",
            "/static/images/clip.jpg",
            0,
            "preview"
        ),
        (
            "鲜时家 硅胶拉伸保鲜膜（已售罄）",
            12.5,
            0,
            "【好物抢先】食品级硅胶保鲜盖，超强弹性拉伸，各种碗碟完美兼容，微波炉冰箱通用，可反复水洗使用，环保省心。",
            "/static/images/silicone_wrap.jpg",
            0,
            "soldout"
        ),
        (
            "鲜时家 智能控温恒温碗（下期预告）",
            88.0,
            0,
            "【好物推荐】内置智能重力控温芯片，长效恒温55度。采用食品级不锈钢内胆与防烫PP材质，是宝宝辅食、冬季温热食材的完美搭档。",
            "/static/images/temp_bowl.jpg",
            0,
            "preview"
        )
    ]

    # 批量将初始商品记录写入数据库
    cursor.executemany('''
    INSERT INTO products (name, price, stock, description, image, is_real, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', products_data)

    # 插入一些初始评价种子数据，展示商城的真实人气与反馈
    reviews_data = [
        (1, "张**", "超级好用的保鲜盒！那个日期拨盘太实用了，家里老人看一眼就知道是什么时候放进去的，再也不会吃过期食品啦！", 5),
        (1, "美食达人小王", "材质很厚实，微波炉加热也没有异味，大号的容量非常大，装洗好的生菜正好。推荐购买！", 5),
        (2, "李*建", "保鲜袋的封口特别严实，装了汤汤水水也完全没有漏，手写区域很大，记日期很方便。", 4)
    ]
    cursor.executemany('''
    INSERT INTO reviews (product_id, username, content, rating)
    VALUES (?, ?, ?, ?)
    ''', reviews_data)

    # 预设几个经典的管理员/商家注册专用邀请码，用于在注册页面激活管理员权限
    invitation_codes = [
        ("XianShiJia2026",),
        ("AdminActiveCode",),
        ("SchoolShowCase",)
    ]
    try:
        # 使用批量插入方式将激活码存入 admin_invitations 表
        cursor.executemany('''
            INSERT INTO admin_invitations (code)
            VALUES (?)
        ''', invitation_codes)
        print("管理员注册激活邀请码预设成功！")
    except sqlite3.IntegrityError:
        # 如果由于唯一性约束导致重复插入，则忽略该异常
        pass

    # 提交事务并关闭数据库连接，释放资源
    conn.commit()
    conn.close()
    print("数据库初始化成功，已生成初始商品和评价数据！")

if __name__ == '__main__':
    # 脚本作为主入口运行时，执行数据库初始化流程
    init_db()
