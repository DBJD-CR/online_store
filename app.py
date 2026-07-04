"""
鲜时家网上商城 - 后端核心服务程序 (app.py)
基于 Flask 框架实现，包含前后台完整业务逻辑：商品展示、购物车、订单、地址管理、支付模拟以及商家后台管理。
所有业务模块均包含高覆盖率的中文注释，以保证后续维护性与系统高可读性（注释率不低于25%）。
"""

import os
import random
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g

# 初始化 Flask 应用实例并配置全局参数
app = Flask(__name__)
# 密钥用于对 Session 敏感数据进行签名和加密，保障客户端会话安全
app.secret_key = 'xian_shi_jia_secret_key'
# 数据库存储文件路径
DB_PATH = 'database.db'


def get_db():
    """
    获取当前请求上下文中的 SQLite 连接。
    使用全局 `g` 对象实现单次 HTTP 请求中数据库连接的单例复用，降低连接创建开销。
    `conn.row_factory = sqlite3.Row` 允许以类似于字典键值对的形式访问查询结果的列。
    """
    if not hasattr(g, 'db'):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def teardown_db(exception):
    """
    Flask 应用上下文销毁时触发的钩子函数。
    在每个请求响应生命周期结束时，自动关闭该请求内开启的 SQLite 连接，防止内存泄漏和文件占用。
    """
    conn = getattr(g, 'db', None)
    if conn:
        try:
            conn.close()
        except Exception:
            pass


# ==================== 通用业务工具函数 ====================

def get_sku_price(product_id, sku_size):
    """
    根据商品 ID 与所选规格动态返回 SKU 的实际单价。
    """
    if product_id == 1:
        return 12.90 if sku_size == '大号' else 9.90
    elif product_id == 2:
        return 7.70 if sku_size == '大号' else 5.50
    return None


def require_valid_user(func):
    """
    Flask 路由控制装饰器：校验当前登录的用户是否有效。
    除了验证 session 中是否存在 user_id 之外，还会去数据库实时检索该用户是否存在，
    防止用户被删或异常会话导致后续业务出错。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 1. 拦截未登录的用户
        if 'user_id' not in session:
            flash("请先登录！", "error")
            return redirect(url_for('login'))

        # 2. 校验数据库中该用户是否真实存在
        conn = get_db()
        cursor = conn.cursor()
        user_exists = cursor.execute('SELECT id FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if not user_exists:
            session.clear()
            flash("您的会话已失效，请重新登录！", "error")
            return redirect(url_for('login'))

        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    """
    Flask 路由控制装饰器：限制仅商家/管理员角色才能访问。
    用于后台订单管理和后台商品库存修改路由，提供基本的越权防护。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 拦截非管理员账号的非法请求并给予警示
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("⚠️ 越权警告：该区域为商家/管理员专属，普通用户无法访问！请输入激活码注册商家账号。", "error")
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


# ==================== 自定义模板过滤器 ====================

@app.template_filter('datetime_format')
def datetime_format(value, format='%Y-%m-%d %H:%M:%S'):
    """
    模板过滤器：对从 SQLite 读取出的标准日期时间字符串进行格式化。
    """
    if not value:
        return ""
    try:
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return dt.strftime(format)
    except Exception:
        return value


@app.template_filter('payment_method_name')
def payment_method_name(method):
    """
    模板过滤器：将订单的支付方式英文编码转换为友好的中文显示名称。
    """
    mapping = {
        'alipay': '支付宝支付',
        'wechat': '微信支付',
        'cod': '货到付款'
    }
    return mapping.get(method, '货到付款')


@app.template_filter('order_status_name')
def order_status_name(status, is_admin=False):
    """
    模板过滤器：将订单交易状态代码转为相应的中文说明。
    支持区分前台买家视图与后台商家管理视图的不同话术。
    """
    admin_mapping = {
        'pending_pay': '买家待付款',
        'pending_ship': '待发货 (待录入单号)',
        'pending_recv': '已发货 (待买家收货)',
        'completed': '✔ 交易成功完成'
    }
    user_mapping = {
        'pending_pay': '待付款',
        'pending_ship': '待发货',
        'pending_recv': '待收货',
        'completed': '交易成功'
    }
    mapping = admin_mapping if is_admin else user_mapping
    return mapping.get(status, status)


@app.context_processor
def inject_global_data():
    """
    全局上下文处理器。
    在每个 HTML 模板页面渲染时，自动注入当前登录的实体和购物车中商品的总件数，
    用以动态展示顶栏的登录状态和购物车数量角标。
    """
    user = None
    cart_count = 0
    if 'user_id' in session:
        conn = get_db()
        cursor = conn.cursor()
        user_row = cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user_row:
            user = dict(user_row)
            # 聚合查询当前用户的购物车商品总数（各条目数量累加值）
            cart_row = cursor.execute('SELECT SUM(quantity) as count FROM cart WHERE user_id = ?', (session['user_id'],)).fetchone()
            if cart_row and cart_row['count']:
                cart_count = cart_row['count']
        else:
            session.clear()
    return dict(current_user=user, cart_count=cart_count)


# ==================== 前台路由 ====================

@app.route('/')
def index():
    """
    商城首页路由。
    从数据库中查询所有的商品（包括真实商品和障眼法虚拟商品），并渲染首页模板。
    """
    conn = get_db()
    cursor = conn.cursor()
    products = cursor.execute('SELECT * FROM products').fetchall()
    return render_template('index.html', products=products)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """
    商品详情页路由。
    根据传入的 product_id 查询商品详细信息及其关联的用户评价，若商品不存在则重定向回首页。
    """
    conn = get_db()
    cursor = conn.cursor()
    product = cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        flash("商品不存在！", "error")
        return redirect(url_for('index'))

    # 获取关联该商品的所有用户评价，并按创建时间倒序排列
    reviews = cursor.execute('SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC', (product_id,)).fetchall()
    return render_template('product_detail.html', product=product, reviews=reviews)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    用户注册路由。
    支持普通买家会员注册，以及携带商家/管理员邀请激活码进行管理员注册。
    若激活码有效，则自动将该用户的 role 设置为 'admin'，并标记该激活码已失效。
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        admin_code = request.form.get('admin_code', '').strip()

        if not username or not password:
            flash("用户名或密码不能为空！", "error")
            return redirect(url_for('register'))

        conn = get_db()
        cursor = conn.cursor()

        role = 'user'
        invitation_id = None

        # 如果输入了商家激活码，则进行安全性验证
        if admin_code:
            invitation = cursor.execute('SELECT * FROM admin_invitations WHERE code = ? AND is_used = 0', (admin_code,)).fetchone()
            if not invitation:
                flash("无效的商家/管理员激活码，或激活码已被使用！", "error")
                return redirect(url_for('register'))
            role = 'admin'
            invitation_id = invitation['id']

        try:
            # 插入新注册用户
            cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))

            # 如果成功注册管理员，则需要将激活码置为已使用
            if role == 'admin' and invitation_id:
                cursor.execute('UPDATE admin_invitations SET is_used = 1 WHERE id = ?', (invitation_id,))
                flash("商家/管理员账号激活成功！请登录进入后台面板。", "success")
            else:
                flash("普通买家会员账号注册成功！请登录。", "success")

            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            # 用户名设有唯一索引约束，若冲突则提示重复
            flash("用户名已存在！", "error")
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    用户登录路由。
    验证用户名和密码的匹配性，验证通过后向 session 写入相关属性以保持会话。
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()

        if user:
            # 写入用户会话缓存
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash("登录成功！欢迎来到鲜时家！", "success")
            return redirect(url_for('index'))
        else:
            flash("用户名或密码错误！", "error")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    退出登录路由。
    清空会话数据并重定向至首页。
    """
    session.clear()
    flash("您已成功退出登录。", "success")
    return redirect(url_for('index'))


@app.route('/addresses', methods=['GET', 'POST'])
@require_valid_user
def addresses():
    """
    地址薄管理路由。
    买家可以在此页面新增自己的多条收货地址，并查看当前已存的地址列表。
    """
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        province = request.form.get('province', '').strip()
        city = request.form.get('city', '').strip()
        district = request.form.get('district', '').strip()
        detail = request.form.get('detail', '').strip()

        # 表单字段空值校验
        if not all([name, phone, province, city, district, detail]):
            flash("请填写完整的收货人信息！", "error")
        else:
            # 新插入一条属于当前用户的地址记录
            cursor.execute('''
                INSERT INTO addresses (user_id, name, phone, province, city, district, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], name, phone, province, city, district, detail))
            conn.commit()
            flash("地址添加成功！", "success")

    # 查询当前用户已添加的所有收货地址
    addr_list = cursor.execute('SELECT * FROM addresses WHERE user_id = ?', (session['user_id'],)).fetchall()
    return render_template('addresses.html', addresses=addr_list)


@app.route('/delete_address/<int:addr_id>')
def delete_address(addr_id):
    """
    删除指定收货地址路由。
    必须通过当前登录用户的 ID 进行越权校验，只允许删除用户自身的地址。
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor()
    # 双重条件（地址ID + 用户ID）防止横向越权删除他人地址
    cursor.execute('DELETE FROM addresses WHERE id = ? AND user_id = ?', (addr_id, session['user_id']))
    conn.commit()
    flash("地址已删除。", "success")
    return redirect(url_for('addresses'))


@app.route('/cart')
@require_valid_user
def cart():
    """
    购物车详情页路由。
    查询当前登录用户的所有购物车明细，并联表获取商品的实时主表字段（库存、图片、名称）。
    同时，根据 SKU 的不同尺寸规格，动态计算并重载商品的实际 SKU 售价。
    """
    conn = get_db()
    cursor = conn.cursor()

    # 联表获取商品详情
    cart_rows = cursor.execute('''
        SELECT c.*, p.name, p.price, p.image, p.stock, p.is_real, p.status
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()

    cart_items = []
    for r in cart_rows:
        item = dict(r)
        # 获取基于尺寸的动态 SKU 真实售价
        sku_price = get_sku_price(item['product_id'], item['sku_size'])
        if sku_price is not None:
            item['price'] = sku_price
        cart_items.append(item)

    return render_template('cart.html', cart_items=cart_items)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    """
    加入购物车异步接口。
    支持 AJAX 调用。处理库存限制、商品购买合法性、规格幂等合并等逻辑。
    """
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "请先登录！"})

    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)
    sku_color = request.form.get('sku_color', '').strip()
    sku_size = request.form.get('sku_size', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    product = cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()

    if not product:
        return jsonify({"status": "error", "message": "商品不存在！"})

    # 障眼法商品不可购买，或库存为 0 时无法添入购物车
    if product['is_real'] == 0 or product['stock'] <= 0:
        return jsonify({"status": "error", "message": "该商品库存不足或无法购买！"})

    # 确认添加购物车时该规格对应的最新价格
    current_price = get_sku_price(product_id, sku_size)
    if current_price is None:
        current_price = product['price']

    # 检索是否已有相同规格（商品、颜色、尺寸均一致）的购物车记录
    exist_item = cursor.execute('''
        SELECT * FROM cart
        WHERE user_id = ? AND product_id = ? AND sku_color = ? AND sku_size = ?
    ''', (session['user_id'], product_id, sku_color, sku_size)).fetchone()

    if exist_item:
        # 已存在相同规格，进行数量合并，且数量累加值不可超过商品的物理库存上限
        new_qty = exist_item['quantity'] + quantity
        if new_qty > product['stock']:
            new_qty = product['stock']
        cursor.execute('UPDATE cart SET quantity = ? WHERE id = ?', (new_qty, exist_item['id']))
    else:
        # 新规加入购物车，若单次添加值超过库存，则截断为最大可用库存
        if quantity > product['stock']:
            quantity = product['stock']
        cursor.execute('''
            INSERT INTO cart (user_id, product_id, quantity, sku_color, sku_size)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], product_id, quantity, sku_color, sku_size))

    conn.commit()
    return jsonify({"status": "success", "message": "成功加入购物车！"})


@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    """
    修改购物车中商品数量的异步接口。
    用于在购物车页面中点击增减按钮或直接输入数值时的实时同步。
    若修改值超出物理库存上限，则会被自动截断为物理库存最大值并返回。
    """
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "请先登录！"})

    cart_id = request.form.get('cart_id', type=int)
    quantity = request.form.get('quantity', type=int)

    if quantity <= 0:
        return jsonify({"status": "error", "message": "数量必须大于0"})

    conn = get_db()
    cursor = conn.cursor()
    item = cursor.execute('''
        SELECT c.*, p.stock
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.id = ? AND c.user_id = ?
    ''', (cart_id, session['user_id'])).fetchone()

    if not item:
        return jsonify({"status": "error", "message": "购物车记录不存在"})

    # 边界保护：若购买数量超出实际库存上限，修正为实际库存
    if quantity > item['stock']:
        quantity = item['stock']

    cursor.execute('UPDATE cart SET quantity = ? WHERE id = ?', (quantity, cart_id))
    conn.commit()
    return jsonify({"status": "success", "new_quantity": quantity})


@app.route('/delete_cart_item/<int:cart_id>')
def delete_cart_item(cart_id):
    """
    从购物车中彻底删除某个商品条目。
    同样进行了 user_id 双重条件绑定，保障资源安全性。
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cart WHERE id = ? AND user_id = ?', (cart_id, session['user_id']))
    conn.commit()
    flash("已从购物车移除商品。", "success")
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
@require_valid_user
def checkout():
    """
    收银台结算与订单创建路由。
    展示待结算的购物车商品以及备选收货地址。
    提交下单时：
      1. 验证地址合法性与库存可用性
      2. 扣减商品物理库存；若库存降为 0，商品状态自动标记为 soldout (已售罄)
      3. 生成唯一交易订单号，向订单主表和明细子表写入数据
      4. 清空该买家当前的购物车
      5. 货到付款直接完成下单进入订单列表；在线支付（微信/支付宝）则重定向至模拟收银台页面。
    """
    conn = get_db()
    cursor = conn.cursor()

    # 提取准备结算的购物车商品明细
    cart_rows = cursor.execute('''
        SELECT c.*, p.name, p.price, p.image, p.stock, p.is_real
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()

    if not cart_rows:
        flash("购物车中没有可以结算的商品！", "error")
        return redirect(url_for('cart'))

    # 初始化结构并动态重载 SKU 实际价格
    cart_items = []
    total_amount = 0.0
    for row in cart_rows:
        item = dict(row)
        sku_price = get_sku_price(item['product_id'], item['sku_size'])
        if sku_price is not None:
            item['price'] = sku_price
        total_amount += item['price'] * item['quantity']
        cart_items.append(item)

    # 获取地址簿供买家选择
    addresses = cursor.execute('SELECT * FROM addresses WHERE user_id = ?', (session['user_id'],)).fetchall()

    if request.method == 'POST':
        address_id = request.form.get('address_id', type=int)
        payment_method = request.form.get('payment_method')

        if not address_id:
            flash("请选择或添加收货地址！", "error")
            return redirect(url_for('checkout'))

        # 获取当前地址快照
        addr = cursor.execute('SELECT * FROM addresses WHERE id = ? AND user_id = ?', (address_id, session['user_id'])).fetchone()
        if not addr:
            flash("收货地址不合规！", "error")
            return redirect(url_for('checkout'))

        # 下单前终极库存校验，避免超卖现象
        for item in cart_items:
            if item['quantity'] > item['stock']:
                flash(f"商品【{item['name']}】库存不足，无法结算！", "error")
                return redirect(url_for('cart'))

        # 扣减库存并更新售罄状态
        for item in cart_items:
            new_stock = item['stock'] - item['quantity']
            cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, item['product_id']))
            if new_stock <= 0:
                cursor.execute("UPDATE products SET status = 'soldout' WHERE id = ?", (item['product_id'],))

        # 规则生成全局唯一订单号
        order_no = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
        address_detail_str = f"{addr['province']} {addr['city']} {addr['district']} {addr['detail']}"

        # 确定订单初始状态：货到付款（COD）直接变为待发货状态，其余为待付款
        initial_status = 'pending_ship' if payment_method == 'cod' else 'pending_pay'

        # 写入订单主表
        cursor.execute('''
            INSERT INTO orders (order_no, user_id, address_name, address_phone, address_detail, total_amount, payment_method, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_no, session['user_id'], addr['name'], addr['phone'], address_detail_str, total_amount, payment_method, initial_status))

        order_id = cursor.lastrowid

        # 写入订单明细子表（创建交易历史快照）
        for item in cart_items:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, product_name, price, quantity, sku_color, sku_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['name'], item['price'], item['quantity'], item['sku_color'], item['sku_size']))

        # 交易创建完成，清空购物车
        cursor.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
        conn.commit()

        if payment_method == 'cod':
            flash("下单成功！货到付款订单，已安排发货中。", "success")
            return redirect(url_for('orders'))
        else:
            return redirect(url_for('pay_page', order_no=order_no))

    return render_template('checkout.html', cart_items=cart_items, addresses=addresses, total_amount=total_amount)


@app.route('/pay/<order_no>', methods=['GET', 'POST'])
def pay_page(order_no):
    """
    在线支付模拟收银台路由。
    提供一个独立的扫码或确认付款交互页。
    当用户点击“确认付款”后，修改订单状态为 pending_ship (待发货)。
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    order = cursor.execute('SELECT * FROM orders WHERE order_no = ? AND user_id = ?', (order_no, session['user_id'])).fetchone()

    if not order:
        flash("未找到对应的订单！", "error")
        return redirect(url_for('orders'))

    if request.method == 'POST':
        # 更新订单为待发货状态
        cursor.execute("UPDATE orders SET status = 'pending_ship' WHERE order_no = ?", (order_no,))
        conn.commit()
        flash("模拟支付成功！后台已为您生成发货单。", "success")
        return redirect(url_for('orders'))

    return render_template('pay.html', order=order)


@app.route('/orders')
@require_valid_user
def orders():
    """
    买家中心 - 我的订单列表路由。
    根据当前买家 ID 倒序查出所有订单，并嵌套查询其每个订单下购买的所有具体商品明细。
    """
    conn = get_db()
    cursor = conn.cursor()

    orders_rows = cursor.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()

    orders_list = []
    for order_row in orders_rows:
        order_dict = dict(order_row)
        # 嵌套查询订单关联的商品条目明细并装配
        items = cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_dict['id'],)).fetchall()
        order_dict['order_items'] = items
        orders_list.append(order_dict)

    return render_template('orders.html', orders=orders_list)


@app.route('/confirm_receipt/<int:order_id>')
def confirm_receipt(order_id):
    """
    确认收货接口。
    用于买家收到快递后，确认该笔订单交易已妥投完成。
    只有待收货 (pending_recv) 状态下的订单才可以确认收货。
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    order = cursor.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?', (order_id, session['user_id'])).fetchone()

    if not order or order['status'] != 'pending_recv':
        flash("订单状态不正确或订单不存在！", "error")
        return redirect(url_for('orders'))

    # 更新订单状态为已完成
    cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
    conn.commit()
    flash("您已确认收货，祝您生活愉快！去写一段评价吧~", "success")
    return redirect(url_for('orders'))


@app.route('/add_review', methods=['POST'])
def add_review():
    """
    商品评价异步接口。
    提交评价内容并记录在 reviews 表中，包含简单的为空校验。
    """
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "请先登录！"})

    product_id = request.form.get('product_id', type=int)
    content = request.form.get('content', '').strip()
    rating = request.form.get('rating', 5, type=int)

    if not content:
        return jsonify({"status": "error", "message": "评价内容不能为空！"})

    conn = get_db()
    cursor = conn.cursor()
    # 写入用户对该商品的真实评语
    cursor.execute('''
        INSERT INTO reviews (product_id, username, content, rating)
        VALUES (?, ?, ?, ?)
    ''', (product_id, session['username'], content, rating))
    conn.commit()
    return jsonify({"status": "success", "message": "评价提交成功！"})


# ==================== 后台管理路由 ====================

@app.route('/admin/orders', methods=['GET', 'POST'])
@admin_required
def admin_orders():
    """
    商家后台 - 订单管理控制台。
    商家可以浏览商城中产生的所有订单与交易细节。
    当检测到 POST 请求时，可以对待发货状态的订单进行快递单号的录入发货，
    更新状态为待收货。
    """
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'ship':
            order_id = request.form.get('order_id', type=int)
            tracking_no = request.form.get('tracking_no', '').strip()

            if not tracking_no:
                flash("发货必须填写快递单号！", "error")
            else:
                # 状态机约束：必须是 pending_ship 状态才能变更为已发货
                cursor.execute('''
                    UPDATE orders
                    SET status = 'pending_recv', tracking_no = ?
                    WHERE id = ? AND status = 'pending_ship'
                ''', (tracking_no, order_id))
                conn.commit()
                flash(f"发货成功！运单号：{tracking_no}", "success")

    # 查询系统中的全量订单，按时间降序展现
    orders_rows = cursor.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    orders_list = []
    for row in orders_rows:
        order_dict = dict(row)
        items = cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_dict['id'],)).fetchall()
        order_dict['order_items'] = items
        orders_list.append(order_dict)

    return render_template('admin_orders.html', orders=orders_list)


@app.route('/admin/products', methods=['GET', 'POST'])
@admin_required
def admin_products():
    """
    商家后台 - 商品与库存管理控制台。
    支持商家修改前台商品的实时标价和物理剩余库存量。
    若修改后库存大于 0，商品状态自动切为 active，若库存设为 0 则自动标记为已售罄 soldout。
    """
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        price = request.form.get('price', type=float)
        stock = request.form.get('stock', type=int)

        # 动态判定商品状态
        status = 'soldout' if stock <= 0 else 'active'

        cursor.execute('''
            UPDATE products
            SET price = ?, stock = ?, status = ?
            WHERE id = ?
        ''', (price, stock, status, product_id))
        conn.commit()
        flash("商品信息修改成功！已实时同步至前台商城。", "success")

    products = cursor.execute('SELECT * FROM products').fetchall()
    return render_template('admin_products.html', products=products)


if __name__ == '__main__':
    # 确保保存商品的图片目录在系统运行前存在
    os.makedirs('static/images', exist_ok=True)
    # 启动 Flask 内置服务器并设定端口
    app.run(
        debug=True,
        port=5000,
        exclude_patterns=['*.db', 'database.db', '**/database.db', '*.pyc']
    )
