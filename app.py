import os
import random
import sqlite3
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

from flask import g

app = Flask(__name__)
app.secret_key = 'xian_shi_jia_secret_key'
DB_PATH = 'database.db'

def get_db():
    # 核心优化：将数据库连接注册到 Flask 的 thread-local 变量 'g' 中。
    # 即使请求抛出异常，也能通过 teardown_appcontext 确保连接 100% 得到安全释放，彻底杜绝 SQLite 句柄和内存泄露！
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if not hasattr(g, 'db_conns'):
        g.db_conns = []
    g.db_conns.append(conn)
    return conn

@app.teardown_appcontext
def teardown_db(exception):
    # 在每个 Flask 请求上下文销毁时，自动关闭该请求生命周期内创建的所有连接
    db_conns = getattr(g, 'db_conns', None)
    if db_conns:
        for conn in db_conns:
            try:
                conn.close()
            except Exception:
                pass

# 自定义过滤器，用于格式化时间
@app.template_filter('datetime_format')
def datetime_format(value, format='%Y-%m-%d %H:%M:%S'):
    if not value:
        return ""
    try:
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return dt.strftime(format)
    except Exception:
        return value

# 全局上下文处理器，注入当前登录状态、购物车商品数等，并对由于数据库重置而失效的会话进行自动清理，维持登录态。
@app.context_processor
def inject_global_data():
    user = None
    cart_count = 0
    if 'user_id' in session:
        conn = get_db()
        cursor = conn.cursor()
        user_row = cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user_row:
            user = dict(user_row)
            # 购物车数量
            cart_row = cursor.execute('SELECT SUM(quantity) as count FROM cart WHERE user_id = ?', (session['user_id'],)).fetchone()
            if cart_row and cart_row['count']:
                cart_count = cart_row['count']
        else:
            # 关键：如果用户在 session 中有 id，但数据库重新初始化后不存在此 ID，必须主动清空 session，彻底修复刷新时残留的脏状态！
            session.clear()
        conn.close()
    return dict(current_user=user, cart_count=cart_count)

# ==================== 前台路由 ====================

# 1. 首页
@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    products = cursor.execute('SELECT * FROM products').fetchall()
    conn.close()
    return render_template('index.html', products=products)

# 2. 商品详情页
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db()
    cursor = conn.cursor()
    product = cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        flash("商品不存在！", "error")
        return redirect(url_for('index'))
    
    # 获取评价列表
    reviews = cursor.execute('SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC', (product_id,)).fetchall()
    conn.close()
    return render_template('product_detail.html', product=product, reviews=reviews)

# 3. 注册 (支持通过管理员/商家专属激活码注册商家账号，拥有后台管理权限)
@app.route('/register', methods=['GET', 'POST'])
def register():
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
        
        # 如果填写了激活邀请码，则校验是否合法且未被使用
        if admin_code:
            invitation = cursor.execute('SELECT * FROM admin_invitations WHERE code = ? AND is_used = 0', (admin_code,)).fetchone()
            if not invitation:
                conn.close()
                flash("无效的商家/管理员激活码，或激活码已被使用！", "error")
                return redirect(url_for('register'))
            role = 'admin'
            invitation_id = invitation['id']
            
        try:
            cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
            
            # 如果是管理员且有激活码，标记该码已被使用
            if role == 'admin' and invitation_id:
                cursor.execute('UPDATE admin_invitations SET is_used = 1 WHERE id = ?', (invitation_id,))
                flash("商家/管理员账号激活成功！请登录进入后台面板。", "success")
            else:
                flash("普通买家会员账号注册成功！请登录。", "success")
                
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("用户名已存在！", "error")
            return redirect(url_for('register'))
        finally:
            conn.close()
            
    return render_template('register.html')

# 4. 登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        conn = get_db()
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']  # 存入角色用于权限检验
            flash("登录成功！欢迎来到鲜时家！", "success")
            return redirect(url_for('index'))
        else:
            flash("用户名或密码错误！", "error")
            return redirect(url_for('login'))
            
    return render_template('login.html')

# 5. 退出登录
@app.route('/logout')
def logout():
    session.clear()
    flash("您已成功退出登录。", "success")
    return redirect(url_for('index'))

# 6. 地址管理
@app.route('/addresses', methods=['GET', 'POST'])
def addresses():
    if 'user_id' not in session:
        flash("请先登录！", "error")
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 强校验数据库中是否存在此用户，防止假登录态绕过
    user_exists = cursor.execute('SELECT id FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if not user_exists:
        conn.close()
        session.clear()
        flash("您的会话已失效，请重新登录！", "error")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        province = request.form.get('province', '').strip()
        city = request.form.get('city', '').strip()
        district = request.form.get('district', '').strip()
        detail = request.form.get('detail', '').strip()
        
        if not all([name, phone, province, city, district, detail]):
            flash("请填写完整的收货人信息！", "error")
        else:
            cursor.execute('''
                INSERT INTO addresses (user_id, name, phone, province, city, district, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], name, phone, province, city, district, detail))
            conn.commit()
            flash("地址添加成功！", "success")
            
    addr_list = cursor.execute('SELECT * FROM addresses WHERE user_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('addresses.html', addresses=addr_list)

# 7. 删除地址
@app.route('/delete_address/<int:addr_id>')
def delete_address(addr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM addresses WHERE id = ? AND user_id = ?', (addr_id, session['user_id']))
    conn.commit()
    conn.close()
    flash("地址已删除。", "success")
    return redirect(url_for('addresses'))

# 8. 购物车列表
@app.route('/cart')
def cart():
    # 强制做强校验：不仅需要 session 中存在 user_id，还需要校验该 user_id 是否在数据库中真实合法
    if 'user_id' not in session:
        flash("请先登录！", "error")
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    user_exists = cursor.execute('SELECT id FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if not user_exists:
        conn.close()
        session.clear()
        flash("您的会话已失效，请重新登录！", "error")
        return redirect(url_for('login'))
    
    cart_rows = cursor.execute('''
        SELECT c.*, p.name, p.price, p.image, p.stock, p.is_real, p.status
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    
    # 将 cart_rows 转换为支持动态 SKU 定价的字典列表传递给模板
    cart_items = []
    for r in cart_rows:
        item = dict(r)
        if item['product_id'] == 1:
            item['price'] = 12.90 if item['sku_size'] == '大号' else 9.90
        elif item['product_id'] == 2:
            item['price'] = 7.70 if item['sku_size'] == '大号' else 5.50
        cart_items.append(item)
        
    conn.close()
    return render_template('cart.html', cart_items=cart_items)

# 9. 加入购物车
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
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
        conn.close()
        return jsonify({"status": "error", "message": "商品不存在！"})
        
    if product['is_real'] == 0 or product['stock'] <= 0:
        conn.close()
        return jsonify({"status": "error", "message": "该商品库存不足或无法购买！"})

    # 动态确定当前 SKU 对应的真实单价
    current_price = product['price']
    if product_id == 1: # 盒子
        current_price = 12.90 if sku_size == '大号' else 9.90
    elif product_id == 2: # 袋子
        current_price = 7.70 if sku_size == '大号' else 5.50
        
    # 检查购物车中是否已有相同 SKU 的商品
    exist_item = cursor.execute('''
        SELECT * FROM cart
        WHERE user_id = ? AND product_id = ? AND sku_color = ? AND sku_size = ?
    ''', (session['user_id'], product_id, sku_color, sku_size)).fetchone()
    
    if exist_item:
        new_qty = exist_item['quantity'] + quantity
        if new_qty > product['stock']:
            new_qty = product['stock']
        cursor.execute('UPDATE cart SET quantity = ? WHERE id = ?', (new_qty, exist_item['id']))
    else:
        if quantity > product['stock']:
            quantity = product['stock']
        cursor.execute('''
            INSERT INTO cart (user_id, product_id, quantity, sku_color, sku_size)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], product_id, quantity, sku_color, sku_size))
        
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "成功加入购物车！"})

# 10. 更新购物车数量
@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "请先登录！"})
        
    cart_id = request.form.get('cart_id', type=int)
    quantity = request.form.get('quantity', type=int)
    
    if quantity <= 0:
        return jsonify({"status": "error", "message": "数量必须大于0"})
        
    conn = get_db()
    cursor = conn.cursor()
    # 获取购物车项和商品库存
    item = cursor.execute('''
        SELECT c.*, p.stock 
        FROM cart c 
        JOIN products p ON c.product_id = p.id 
        WHERE c.id = ? AND c.user_id = ?
    ''', (cart_id, session['user_id'])).fetchone()
    
    if not item:
        conn.close()
        return jsonify({"status": "error", "message": "购物车记录不存在"})
        
    if quantity > item['stock']:
        quantity = item['stock']
        
    cursor.execute('UPDATE cart SET quantity = ? WHERE id = ?', (quantity, cart_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "new_quantity": quantity})

# 11. 删除购物车记录
@app.route('/delete_cart_item/<int:cart_id>')
def delete_cart_item(cart_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cart WHERE id = ? AND user_id = ?', (cart_id, session['user_id']))
    conn.commit()
    conn.close()
    flash("已从购物车移除商品。", "success")
    return redirect(url_for('cart'))

# 12. 确认下单页
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash("请先登录！", "error")
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    
    # 获取选中的购物车项 (这里我们直接让购物车全部结算，符合10年代的简单特性)
    cart_rows = cursor.execute('''
        SELECT c.*, p.name, p.price, p.image, p.stock, p.is_real
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    
    if not cart_rows:
        conn.close()
        flash("购物车中没有可以结算的商品！", "error")
        return redirect(url_for('cart'))
        
    # 动态转换购物车商品属性并计算对应规格的价格
    cart_items = []
    total_amount = 0.0
    for row in cart_rows:
        item = dict(row)
        if item['product_id'] == 1:
            item['price'] = 12.90 if item['sku_size'] == '大号' else 9.90
        elif item['product_id'] == 2:
            item['price'] = 7.70 if item['sku_size'] == '大号' else 5.50
        total_amount += item['price'] * item['quantity']
        cart_items.append(item)
        
    # 地址列表
    addresses = cursor.execute('SELECT * FROM addresses WHERE user_id = ?', (session['user_id'],)).fetchall()
    
    if request.method == 'POST':
        address_id = request.form.get('address_id', type=int)
        payment_method = request.form.get('payment_method')
        
        if not address_id:
            flash("请选择或添加收货地址！", "error")
            conn.close()
            return redirect(url_for('checkout'))
            
        addr = cursor.execute('SELECT * FROM addresses WHERE id = ? AND user_id = ?', (address_id, session['user_id'])).fetchone()
        if not addr:
            flash("收货地址不合规！", "error")
            conn.close()
            return redirect(url_for('checkout'))
            
        # 验证商品库存
        for item in cart_items:
            if item['quantity'] > item['stock']:
                flash(f"商品【{item['name']}】库存不足，无法结算！", "error")
                conn.close()
                return redirect(url_for('cart'))
        
        # 扣减库存
        for item in cart_items:
            new_stock = item['stock'] - item['quantity']
            cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, item['product_id']))
            # 如果库存减为0，自动变更为售罄状态
            if new_stock <= 0:
                cursor.execute("UPDATE products SET status = 'soldout' WHERE id = ?", (item['product_id'],))
        
        # 创建订单
        order_no = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
        address_detail_str = f"{addr['province']} {addr['city']} {addr['district']} {addr['detail']}"
        
        # 货到付款直接是待发货状态，其他是待付款状态
        initial_status = 'pending_ship' if payment_method == 'cod' else 'pending_pay'
        
        cursor.execute('''
            INSERT INTO orders (order_no, user_id, address_name, address_phone, address_detail, total_amount, payment_method, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_no, session['user_id'], addr['name'], addr['phone'], address_detail_str, total_amount, payment_method, initial_status))
        
        order_id = cursor.lastrowid
        
        # 写入订单明细 (保存此时动态计算得到的 SKU 定价)
        for item in cart_items:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, product_name, price, quantity, sku_color, sku_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['name'], item['price'], item['quantity'], item['sku_color'], item['sku_size']))
            
        # 清空购物车
        cursor.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
        conn.commit()
        conn.close()
        
        if payment_method == 'cod':
            flash("下单成功！货到付款订单，已安排发货中。", "success")
            return redirect(url_for('orders'))
        else:
            # 跳转去模拟支付页
            return redirect(url_for('pay_page', order_no=order_no))
            
    conn.close()
    return render_template('checkout.html', cart_items=cart_items, addresses=addresses, total_amount=total_amount)

# 13. 模拟支付页
@app.route('/pay/<order_no>', methods=['GET', 'POST'])
def pay_page(order_no):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    order = cursor.execute('SELECT * FROM orders WHERE order_no = ? AND user_id = ?', (order_no, session['user_id'])).fetchone()
    
    if not order:
        conn.close()
        flash("未找到对应的订单！", "error")
        return redirect(url_for('orders'))
        
    if request.method == 'POST':
        # 确认付款，更新订单状态
        cursor.execute("UPDATE orders SET status = 'pending_ship' WHERE order_no = ?", (order_no,))
        conn.commit()
        conn.close()
        flash("模拟支付成功！后台已为您生成发货单。", "success")
        return redirect(url_for('orders'))
        
    conn.close()
    return render_template('pay.html', order=order)

# 14. 个人中心-订单列表
@app.route('/orders')
def orders():
    if 'user_id' not in session:
        flash("请先登录！", "error")
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    
    # 强校验数据库中是否存在此用户，防止假登录态绕过
    user_exists = cursor.execute('SELECT id FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if not user_exists:
        conn.close()
        session.clear()
        flash("您的会话已失效，请重新登录！", "error")
        return redirect(url_for('login'))

    # 查询订单
    orders_rows = cursor.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    
    orders_list = []
    for order_row in orders_rows:
        order_dict = dict(order_row)
        # 查询明细
        items = cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_dict['id'],)).fetchall()
        order_dict['items'] = items
        orders_list.append(order_dict)
        
    conn.close()
    return render_template('orders.html', orders=orders_list)

# 15. 确认收货
@app.route('/confirm_receipt/<int:order_id>')
def confirm_receipt(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    order = cursor.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?', (order_id, session['user_id'])).fetchone()
    
    if not order or order['status'] != 'pending_recv':
        conn.close()
        flash("订单状态不正确或订单不存在！", "error")
        return redirect(url_for('orders'))
        
    cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    flash("您已确认收货，祝您生活愉快！去写一段评价吧~", "success")
    return redirect(url_for('orders'))

# 16. 发表评价
@app.route('/add_review', methods=['POST'])
def add_review():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "请先登录！"})
        
    product_id = request.form.get('product_id', type=int)
    content = request.form.get('content', '').strip()
    rating = request.form.get('rating', 5, type=int)
    
    if not content:
        return jsonify({"status": "error", "message": "评价内容不能为空！"})
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reviews (product_id, username, content, rating)
        VALUES (?, ?, ?, ?)
    ''', (product_id, session['username'], content, rating))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "评价提交成功！"})


# ==================== 后台管理路由 (限制仅管理员角色才能进入) ====================

# 验证管理员权限装饰器
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("⚠️ 越权警告：该区域为商家/管理员专属，普通用户无法访问！请输入激活码注册商家账号。", "error")
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

# 1. 后台订单管理列表
@app.route('/admin/orders', methods=['GET', 'POST'])
@admin_required
def admin_orders():
    conn = get_db()
    cursor = conn.cursor()
    
    # 模拟手动发货逻辑
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'ship':
            order_id = request.form.get('order_id', type=int)
            tracking_no = request.form.get('tracking_no', '').strip()
            
            if not tracking_no:
                flash("发货必须填写快递单号！", "error")
            else:
                cursor.execute('''
                    UPDATE orders 
                    SET status = 'pending_recv', tracking_no = ? 
                    WHERE id = ? AND status = 'pending_ship'
                ''', (tracking_no, order_id))
                conn.commit()
                flash(f"发货成功！运单号：{tracking_no}", "success")
                
    orders_rows = cursor.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    orders_list = []
    for row in orders_rows:
        order_dict = dict(row)
        items = cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_dict['id'],)).fetchall()
        order_dict['items'] = items
        orders_list.append(order_dict)
        
    conn.close()
    return render_template('admin_orders.html', orders=orders_list)

# 2. 后台商品管理列表 (修改价格和库存)
@app.route('/admin/products', methods=['GET', 'POST'])
@admin_required
def admin_products():
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        price = request.form.get('price', type=float)
        stock = request.form.get('stock', type=int)
        
        # 判断如果库存是 0，自动变为 soldout 状态，否则变为 active 状态
        status = 'soldout' if stock <= 0 else 'active'
        
        cursor.execute('''
            UPDATE products 
            SET price = ?, stock = ?, status = ?
            WHERE id = ?
        ''', (price, stock, status, product_id))
        conn.commit()
        flash("商品信息修改成功！已实时同步至前台商城。", "success")
        
    products = cursor.execute('SELECT * FROM products').fetchall()
    conn.close()
    return render_template('admin_products.html', products=products)


if __name__ == '__main__':
    # 确保 static 文件夹存在，以便后续存放商品图
    os.makedirs('static/images', exist_ok=True)
    # 核心优化：利用 exclude_patterns 明确排除 *.db 和 database.db。
    # 这样当 SQLite 写入或更新数据时，Flask Reloader 不会错误地触发频繁重载，彻底避免 Windows 环境下旧进程挂起、内存累积 OOM 的致命隐患！
    app.run(
        debug=True,
        port=5000,
        exclude_patterns=['*.db', 'database.db', '**/database.db', '*.pyc']
    )
