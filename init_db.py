import sqlite3
import os

DB_PATH = 'database.db'

def init_db():
    # 如果数据库文件已存在，则删除，以便重新初始化
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("已检测到旧数据库，已清理。")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 用户表 (新增 role 字段标记用户权限，'admin' 为管理员，'user' 为普通用户)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )
    ''')

    # 1.5 邀请码/激活码表 (用于注册时激活商家/管理员权限)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        is_used INTEGER NOT NULL DEFAULT 0
    )
    ''')

    # 2. 收货地址表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        province TEXT NOT NULL,
        city TEXT NOT NULL,
        district TEXT NOT NULL,
        detail TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 3. 商品表
    # is_real: 1 表示真实可售，0 表示虚拟展示
    # status: 'active' (正常), 'soldout' (已售罄), 'preview' (下期预告)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        description TEXT,
        image TEXT,
        is_real INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active'
    )
    ''')

    # 4. 购物车表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        sku_color TEXT,
        sku_size TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')

    # 5. 订单表
    # status: 'pending_pay' (待付款), 'pending_ship' (待发货), 'pending_recv' (待收货), 'completed' (已完成)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        address_name TEXT NOT NULL,
        address_phone TEXT NOT NULL,
        address_detail TEXT NOT NULL,
        total_amount REAL NOT NULL,
        payment_method TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_pay',
        tracking_no TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 6. 订单明细表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        sku_color TEXT,
        sku_size TEXT,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')

    # 7. 评价表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        content TEXT NOT NULL,
        rating INTEGER NOT NULL DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )
    ''')

    # 插入初始商品数据（新增第6个虚拟障眼商品，满足3列排版下左右完美的 6 个格子）
    # 按照要求设定真实商品价格：
    # 盒子：大号 12.90 元，小号 9.90 元（这里把主商品表的基础定价设为大号的 12.90 元）
    # 袋子：大号 7.70 元，小号 5.50 元（这里把主商品表的基础定价设为大号的 7.70 元）
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

    cursor.executemany('''
    INSERT INTO products (name, price, stock, description, image, is_real, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', products_data)

    # 插入一些初始评价
    reviews_data = [
        (1, "张**", "超级好用的保鲜盒！那个日期拨盘太实用了，家里老人看一眼就知道是什么时候放进去的，再也不会吃过期食品啦！", 5),
        (1, "美食达人小王", "材质很厚实，微波炉加热也没有异味，大号的容量非常大，装洗好的生菜正好。推荐购买！", 5),
        (2, "李*建", "保鲜袋的封口特别严实，装了汤汤水水也完全没有漏，手写区域很大，记日期很方便。", 4)
    ]
    cursor.executemany('''
    INSERT INTO reviews (product_id, username, content, rating)
    VALUES (?, ?, ?, ?)
    ''', reviews_data)

    # 预设几个经典的管理员/商家注册专用邀请码
    invitation_codes = [
        ("XianShiJia2026",),
        ("AdminActiveCode",),
        ("SchoolShowCase",)
    ]
    try:
        cursor.executemany('''
            INSERT INTO admin_invitations (code)
            VALUES (?)
        ''', invitation_codes)
        print("管理员注册激活邀请码预设成功！")
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()
    print("数据库初始化成功，已生成初始商品和评价数据！")

if __name__ == '__main__':
    init_db()
