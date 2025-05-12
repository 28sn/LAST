from flask import Flask, render_template, jsonify, request, redirect, url_for
from datetime import datetime
from collections import OrderedDict
from pyzbar.pyzbar import decode
import threading
import requests
import time
import os
import cv2
import scan  # استيراد ملف scan.py
from scan import get_product_info  # استيراد دالة get_product_info من scan.py
from flask import jsonify
import qrcode
from flask import send_file
from io import BytesIO
from flask import Flask, render_template, request, redirect, session, url_for
import json
from flask import session
from collections import Counter
from datetime import datetime, timedelta
from flask import g
from werkzeug.utils import secure_filename
import uuid


app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)  # مجلد المشروع الحالي
app.secret_key = "super_secret_key"
USER_FILE = os.path.join(BASE_DIR, "users.json")
RECIPE_FILE = os.path.join(BASE_DIR, "recipes.txt")
SHOPPING_FILE = os.path.join(BASE_DIR, "shopping_cart.txt")
USAGE_LOG = os.path.join(BASE_DIR, "usage_log.txt")
visit_counter = 0  # عداد مؤقت (يمكن تخزينه لاحقًا في ملف إذا تبغى)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
POSTS_FILE = os.path.join(BASE_DIR, "posts.json")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def load_posts():
    if not os.path.exists(POSTS_FILE):
        return []
    with open(POSTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_posts(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


@app.route("/upload_post", methods=["GET", "POST"])
def upload_post():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if "image" not in request.files:
            return "❌ لا يوجد ملف صورة"

        file = request.files["image"]
        if file.filename == "":
            return "❌ اسم الملف فارغ"

        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(filepath)

        caption = request.form.get("caption", "").strip()
        post = {
            "id": str(uuid.uuid4()),  # ← أضف هذا لكل منشور
            "username": session["user"],
            "image": f"/static/uploads/{unique_name}",
            "caption": caption,
            "likes": 0,
            "comments": [],
            "timestamp": datetime.now().isoformat()
        }

        posts = load_posts()
        posts.append(post)
        save_posts(posts)

        return redirect(url_for("view_posts"))

    return render_template("upload_post.html")
def user_file(name):
    username = session.get("user")
    return os.path.join(BASE_DIR, f"{name}_{username}.txt") if username else None

def get_total_calories(username):
    path = os.path.join(BASE_DIR, f"product_info_{username}.txt")
    total = 0
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        blocks = f.read().strip().split("="*50)
        for block in blocks:
            lines = block.strip().splitlines()
            for line in lines:
                if line.lower().startswith("energy:"):
                    try:
                        kcal = line.split(":", 1)[1].strip().replace("kcal", "")
                        total += float(kcal or 0)
                    except:
                        continue
    return round(total)
@app.route('/scan', methods=['POST'])
def scan_barcode():
    # استلام الصورة من العميل
    image = request.files['image']
    image_path = 'temp_image.jpg'
    image.save(image_path)
    
    # قراءة الصورة باستخدام OpenCV
    img = cv2.imread(image_path)

    # معالجة الصورة (تحويل الصورة إلى تدرجات الرمادي وتحسينها)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)
    
    # استخراج الباركود باستخدام pyzbar
    decoded_objects = decode(thresh)
    if decoded_objects:
        barcode_data = decoded_objects[0].data.decode('utf-8')
        product_info = get_product_info(barcode_data)
        if product_info:
            return jsonify({"success": True, "product_info": product_info})
        else:
            return jsonify({"success": False, "message": "لم يتم العثور على المنتج"})
    else:
        return jsonify({"success": False, "message": "لم يتم العثور على الباركود في الصورة"})

@app.route("/view_posts")
def view_posts():
    posts = load_posts()[::-1]  # عكس الترتيب لعرض الأحدث أولاً
    return render_template("view_posts.html", posts=posts)

@app.route("/api/posts")
def api_posts():
    return jsonify(load_posts()[::-1])
@app.route("/api/posts/like", methods=["POST"])
def like_post():
    data = request.json
    post_id = data.get("id")
    posts = load_posts()
    for post in posts:
        if post["id"] == post_id:
            post["likes"] += 1
            break
    save_posts(posts)
    return jsonify({"success": True})



def get_cleaning_count(username):
    path = os.path.join(BASE_DIR, f"cleaning_log_{username}.txt")
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return len([line for line in f if line.strip()])
# دالة لقراءة المنتجات من ملف النص
def read_products():
    username = session.get("user")
    if not username:
        return []

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")
    if not os.path.exists(user_product_file):
        return []

    with open(user_product_file, "r", encoding="utf-8") as f:
        content = f.read().strip()

    blocks = content.split("==================================================")
    products = []

    for block in blocks:
        lines = block.strip().splitlines()
        data = {}

        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip().lower()
                val = val.strip()

                if key == "product name":
                    data["name"] = val
                elif key == "brand":
                    data["brand"] = val
                elif key == "ingredients":
                    data["ingredients"] = val
                elif key == "energy":
                    data["energy"] = val.replace("kcal", "").strip()
                elif key == "expiration date":
                    data["expires"] = val
                elif key == "barcode":
                    data["barcode"] = val

        if data:
            products.append(data)

    return products



@app.route("/users")
def users_page():
    return render_template("users.html")
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
@app.route("/api/user_info")
def user_info():
    return jsonify({"username": session.get("user", "زائر")})
def save_user(username, password, role="user"):
    users = load_users()
    if username in users:
        return False
    users[username] = {
        "password": password,
        "role": role,
        "visits": 0,
        "online": False
    }
    with open(USER_FILE, "w") as f:
        json.dump(users, f)
    # إنشاء ملفات المستخدم الفارغة عند التسجيل
    open(os.path.join(BASE_DIR, f"product_info_{username}.txt"), "w", encoding="utf-8").close()
    open(os.path.join(BASE_DIR, f"shopping_cart_{username}.txt"), "w", encoding="utf-8").close()
    open(os.path.join(BASE_DIR, f"usage_log_{username}.txt"), "w", encoding="utf-8").close()

    return True

def increment_login_count(username):
    users = load_users()
    if username in users:
        users[username]["login_count"] = users[username].get("login_count", 0) + 1
        with open(USER_FILE, "w") as f:
            json.dump(users, f)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        users = load_users()
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username]["password"] == password:
            increment_login_count(username)
            session["user"] = username
            session["role"] = users[username].get("role", "user")

            # ✅ أنشئ ملف الاستخدام إذا غير موجود
            usage_file = os.path.join(BASE_DIR, f"usage_log_{username}.txt")
            if not os.path.exists(usage_file):
                open(usage_file, "w", encoding="utf-8").close()

            return redirect(url_for("index"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/api/delete_user", methods=["POST"])
def delete_user():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "ليس لديك صلاحية"}), 403

    data = request.json
    target_user = data.get("username")

    if target_user == session["user"]:
        return jsonify({"success": False, "message": "لا يمكنك حذف نفسك"}), 400

    users = load_users()
    if target_user in users:
        del users[target_user]
        with open(USER_FILE, "w") as f:
            json.dump(users, f)

        # حذف ملفات المستخدم
        for prefix in ["product_info", "shopping_cart", "usage_log"]:
            file_path = os.path.join(BASE_DIR, f"{prefix}_{target_user}.txt")
            if os.path.exists(file_path):
                os.remove(file_path)

        return jsonify({"success": True})

    return jsonify({"success": False, "message": "المستخدم غير موجود"})

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = "user"  # ثابت لكل المستخدمين الجدد

        success = save_user(username, password, role)
        if success:
            session["user"] = username
            session["role"] = role
            return redirect(url_for("index"))
        return render_template("register.html", error="Username already exists")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
@app.before_request
def protect():
    public_routes = ["login", "register", "static"]
    if request.endpoint and request.endpoint not in public_routes and "user" not in session:
        return redirect(url_for("login"))

@app.route("/api/qr_shopping")
def generate_shopping_qr():
    cart = read_cart()
    if not cart:
        return jsonify({"message": "🧺 السلة فارغة"})

    content = "\n".join([f"- {item['name']} × {item['quantity']}" for item in cart])

    qr = qrcode.make(content)
    img_io = BytesIO()
    qr.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')
@app.route("/api/products")
def get_all_products():
    products = read_products()  # قراءة المنتجات من ملف النص
    return jsonify(products)  # إرسال البيانات في شكل JSON


@app.route("/delete_product", methods=["POST"])
def delete_product():
    username = session.get("user")
    if not username:
        return redirect(url_for("login"))

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

    product_name = request.form["product_name"].strip().lower()
    products = read_products()  # قراءة جميع المنتجات من ملف المستخدم
    updated_products = [p for p in products if p['name'].lower() != product_name]

    # إعادة كتابة الملف بعد الحذف
    with open(user_product_file, "w", encoding="utf-8") as f:
        for product in updated_products:
            f.write(f"Product Information:\n")
            f.write(f"Product Name: {product['name']}\n")
            f.write(f"Brand: {product['brand']}\n")
            f.write(f"Ingredients: {product['ingredients']}\n")
            f.write(f"Energy: {product['energy']}\n")
            f.write(f"Expiration Date: {product['expires']}\n")
            f.write(f"Barcode: {product['barcode']}\n")
            if 'quantity' in product:
                f.write(f"Quantity: {product['quantity']}\n")
            f.write("="*50 + "\n")

    return redirect(url_for("inventory"))

# دالة لقراءة الوصفات من ملف النص
def read_recipes():
    if not os.path.exists(RECIPE_FILE):
        return []
    with open(RECIPE_FILE, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()
    recipes = []
    current = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("name:"):
            if current:
                recipes.append(current)
            current = {"name": line.replace("name:", "").strip(), "ingredients": []}
        elif line.startswith("ingredients:"):
            ing = line.replace("ingredients:", "").strip()
            current["ingredients"] = [i.strip().lower() for i in ing.split(",")]
    if current:
        recipes.append(current)
    return recipes

# دالة لقراءة سلة التسوق من ملف النص
def read_cart():
    username = session.get("user")
    if not username:
        return []

    user_cart_file = os.path.join(BASE_DIR, f"shopping_cart_{username}.txt")

    if not os.path.exists(user_cart_file):
        return []

    with open(user_cart_file, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()

    cart = {}
    for line in lines:
        item = line.strip().lower()
        if item:
            cart[item] = cart.get(item, 0) + 1

    return [{"name": name, "quantity": qty} for name, qty in cart.items()]

# دالة لإضافة عنصر إلى سلة التسوق
def add_to_cart(items):
    username = session.get("user")
    if not username:
        return  # أو يمكنك raise Exception("User not logged in")

    user_cart_file = os.path.join(BASE_DIR, f"shopping_cart_{username}.txt")
    with open(user_cart_file, "a", encoding="utf-8") as f:
        for item in items:
            f.write(item.strip().lower() + "\n")


@app.route("/")
def index():
    username = session.get("user")
    if username:
        users = load_users()
        if username in users:
            users[username]["visits"] = users[username].get("visits", 0) + 1
            with open(USER_FILE, "w") as f:
                json.dump(users, f, indent=2)

    # ✅ زيادة عداد الزيارات
    stats_file = os.path.join(BASE_DIR, "stats.json")
    if os.path.exists(stats_file):
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
    else:
        stats = {"total_visits": 0}

    stats["total_visits"] += 1

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    return render_template("index.html")
@app.route("/api/site_stats")
def site_stats():
    stats_file = os.path.join(BASE_DIR, "stats.json")
    users = load_users()

    if os.path.exists(stats_file):
        with open(stats_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
    else:
        stats = {"total_visits": 0}

    return jsonify({
        "total_users": len(users),
        "total_visits": stats.get("total_visits", 0)
    })

@app.route("/alerts")
def alerts():
    today = datetime.today()  # التاريخ الحالي
    products = read_products()  # قراءة جميع المنتجات من ملف النص
    alerts = {"expired": [], "ok": [], "soon": []}  # تصنيف التنبيهات إلى ثلاث فئات

    for product in products:
        if "expires" in product and product["expires"]:
            try:
                # تحويل تاريخ الانتهاء إلى كائن datetime
                exp = datetime.strptime(product["expires"], "%Y-%m-%d")
                diff = (exp - today).days  # الفرق بين تاريخ اليوم وتاريخ الانتهاء

                # تصنيف المنتج بناءً على تاريخ الانتهاء
                if diff < 0:
                    product["status"] = "expired"  # المنتج انتهت صلاحيتها
                    alerts["expired"].append(product)
                elif diff <= 30:
                    product["status"] = "soon"  # المنتج سينتهي قريبًا
                    alerts["soon"].append(product)
                else:
                    product["status"] = "ok"  # المنتج صالح
                    alerts["ok"].append(product)
            except Exception as e:
                print(f"Error processing expiration date for product {product['name']}: {e}")
                continue  # إذا فشل في معالجة تاريخ الانتهاء، يتم تجاهل هذا المنتج

    # تمرير المتغير alerts إلى القالب
    return render_template("alerts.html", alerts=alerts)



@app.route("/inventory")
def inventory():
    products = read_products()  # قراءة المنتجات من ملف النص
    return render_template("inventory.html", products=products)

@app.route("/recipes")
def recipes():
    return render_template("recipes.html")

@app.route("/shopping")
def shopping():
    cart = read_cart()
    return render_template("shopping.html", cart=cart)


@app.route("/products")
def get_products():
    return jsonify(read_products())

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/healthy_tips")
def healthy_tips():
    return render_template("healthy_tips.html")
@app.route("/cleaning")
def cleaning_reminder():
    return render_template("cleaning_reminder.html")

@app.route("/settings/allergy")
def allergy_settings():
    return render_template("settings/allergy.html")
@app.route("/add_product_choice")
def add_product_choice():
    return render_template("add_product_choice.html")

@app.route("/scan_remove")
def scan_remove():
    return render_template("scan_remove.html")
@app.route("/api/remove_product_by_barcode")
def remove_by_barcode():
    username = session.get("user")
    if not username:
        return jsonify({"success": False, "message": "يجب تسجيل الدخول أولاً"})

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

    barcode = request.args.get("barcode", "").strip()
    if not barcode:
        return jsonify({"success": False, "message": "الباركود مفقود"})

    products = read_products()
    updated = [p for p in products if p["barcode"] != barcode]

    if len(updated) == len(products):
        return jsonify({"success": False, "message": "المنتج غير موجود"})

    with open(user_product_file, "w", encoding="utf-8") as f:
        for product in updated:
            f.write(f"Product Information:\n")
            f.write(f"Product Name: {product['name']}\n")
            f.write(f"Brand: {product['brand']}\n")
            f.write(f"Ingredients: {product['ingredients']}\n")
            f.write(f"Energy: {product['energy']}\n")
            f.write(f"Expiration Date: {product['expires']}\n")
            f.write(f"Barcode: {product['barcode']}\n")
            if 'quantity' in product:
                f.write(f"Quantity: {product['quantity']}\n")
            f.write("="*50 + "\n")

    return jsonify({"success": True})

@app.route("/api/remove_product_by_name", methods=["POST"])
def remove_by_name():
    username = session.get("user")
    if not username:
        return jsonify({"success": False, "message": "يجب تسجيل الدخول أولاً"})

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

    data = request.json
    name = data.get("name", "").strip().lower()
    if not name:
        return jsonify({"success": False, "message": "الاسم مفقود"})

    products = read_products()
    updated = [p for p in products if p["name"].lower() != name]

    with open(user_product_file, "w", encoding="utf-8") as f:
        for product in updated:
            f.write(f"Product Information:\n")
            f.write(f"Product Name: {product['name']}\n")
            f.write(f"Brand: {product['brand']}\n")
            f.write(f"Ingredients: {product['ingredients']}\n")
            f.write(f"Energy: {product['energy']}\n")
            f.write(f"Expiration Date: {product['expires']}\n")
            f.write(f"Barcode: {product['barcode']}\n")
            if 'quantity' in product:
                f.write(f"Quantity: {product['quantity']}\n")
            f.write("="*50 + "\n")

    return jsonify({"success": True})
@app.route("/post/<post_id>")
def view_post(post_id):
    if "user" not in session:
        return redirect(url_for("login"))

    posts = load_posts()
    for post in posts:
        if post["id"] == post_id:
            return render_template(
                "view_post.html",
                post=post,
                current_user=session["user"],
                current_role=session.get("role", "user")
            )
    return "لم يتم العثور على المنشور", 404

@app.route("/post/<post_id>/like", methods=["POST"])
def like_post_page(post_id):
    posts = load_posts()
    for post in posts:
        if post["id"] == post_id:
            post["likes"] += 1
            save_posts(posts)
            break
    return redirect(url_for("view_post", post_id=post_id))
@app.route("/post/<post_id>/comment", methods=["POST"])
def comment_post(post_id):
    comment_text = request.form.get("comment", "").strip()
    username = session.get("user")
    if not comment_text or not username:
        return "❌ التعليق أو المستخدم فارغ"

    posts = load_posts()
    for post in posts:
        if post["id"] == post_id:
            post["comments"].append({
                "author": username,
                "text": comment_text
            })
            break
    save_posts(posts)
    return redirect(url_for("view_post", post_id=post_id))


@app.route("/api/old_count")
def old_product_count():
    username = session.get("user")
    if not username:
        return jsonify({"error": "يجب تسجيل الدخول"}), 401

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")
    count = 0

    if os.path.exists(user_product_file):
        with open(user_product_file, "r", encoding="utf-8") as f:
            content = f.read().strip().split("=" * 50)
            for block in content:
                lines = block.strip().splitlines()
                for line in lines:
                    if "Expiration Date" in line:
                        try:
                            date_str = line.split(":", 1)[1].strip()
                            exp = datetime.strptime(date_str, "%Y-%m-%d")
                            if exp < datetime.today():
                                count += 1
                        except:
                            continue

    return jsonify({"count": count})

@app.route("/use_product")
def use_product():
    return render_template("use_product.html")

@app.route("/api/grouped_products")
def grouped_products():
    products = read_products()
    grouped = {}
    for p in products:
        name = p["name"].lower()
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(p)
    for name in grouped:
        grouped[name].sort(key=lambda x: x.get("expires", "9999-12-31"))
    return jsonify(grouped)
@app.route("/use_full", methods=["POST"])
def use_full():
    username = session.get("user")
    if not username:
        return "يجب تسجيل الدخول أولاً"

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")
    user_usage_file = os.path.join(BASE_DIR, f"usage_log_{username}.txt")

    barcode = request.form["barcode"].strip()
    if not barcode:
        return "Invalid barcode"

    products = read_products()
    updated = []
    for p in products:
        if p["barcode"] == barcode:
            with open(user_usage_file, "a", encoding="utf-8") as log:
                log.write(f"Name: {p['name']}\n")
                log.write(f"Barcode: {p['barcode']}\n")
                log.write(f"Used: full\n")
                log.write(f"Date: {datetime.today().strftime('%Y-%m-%d')}\n")
                log.write("="*40 + "\n")
            continue
        else:
            updated.append(p)

    with open(user_product_file, "w", encoding="utf-8") as f:
        for p in updated:
            f.write("Product Information:\n")
            f.write(f"Product Name: {p['name']}\n")
            f.write(f"Brand: {p['brand']}\n")
            f.write(f"Ingredients: {p['ingredients']}\n")
            f.write(f"Energy: {p['energy']}\n")
            f.write(f"Expiration Date: {p['expires']}\n")
            f.write(f"Barcode: {p['barcode']}\n")
            if 'quantity' in p:
                f.write(f"Quantity: {p['quantity']}\n")
            f.write("="*50 + "\n")

    return redirect(url_for("use_product"))

@app.route("/use_partial", methods=["POST"])
def use_partial():
    username = session.get("user")
    if not username:
        return "يجب تسجيل الدخول أولاً"

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")
    user_usage_file = os.path.join(BASE_DIR, f"usage_log_{username}.txt")

    barcode = request.form["barcode"].strip()
    try:
        used_amount = float(request.form["amount"])
    except:
        return "⚠️ كمية غير صالحة"

    products = read_products()
    updated = []
    for p in products:
        if p["barcode"] == barcode:
            quantity = float(p.get("quantity", 1))
            remaining = quantity - used_amount
            if remaining > 0:
                p["quantity"] = round(remaining, 2)
                updated.append(p)
                with open(user_usage_file, "a", encoding="utf-8") as log:
                    log.write(f"Name: {p['name']}\n")
                    log.write(f"Barcode: {p['barcode']}\n")
                    log.write(f"Used: partial ({used_amount})\n")
                    log.write(f"Date: {datetime.today().strftime('%Y-%m-%d')}\n")
                    log.write("="*40 + "\n")
            else:
                with open(user_usage_file, "a", encoding="utf-8") as log:
                    log.write(f"Name: {p['name']}\n")
                    log.write(f"Barcode: {p['barcode']}\n")
                    log.write(f"Used: full (via partial)\n")
                    log.write(f"Date: {datetime.today().strftime('%Y-%m-%d')}\n")
                    log.write("="*40 + "\n")
        else:
            updated.append(p)

    with open(user_product_file, "w", encoding="utf-8") as f:
        for p in updated:
            f.write("Product Information:\n")
            f.write(f"Product Name: {p['name']}\n")
            f.write(f"Brand: {p['brand']}\n")
            f.write(f"Ingredients: {p['ingredients']}\n")
            f.write(f"Energy: {p['energy']}\n")
            f.write(f"Expiration Date: {p['expires']}\n")
            f.write(f"Barcode: {p['barcode']}\n")
            if 'quantity' in p:
                f.write(f"Quantity: {p['quantity']}\n")
            f.write("="*50 + "\n")

    return redirect(url_for("use_product"))

@app.route("/api/alerts")
def get_alerts():
    today = datetime.today()  # التاريخ الحالي
    products = read_products()  # قراءة المنتجات من ملف النص
    alerts = {"expired": [], "ok": [], "soon": []}  # تصنيف التنبيهات إلى ثلاث فئات
    
    for product in products:
        if "expires" in product and product["expires"]:
            try:
                # تحويل تاريخ الانتهاء إلى كائن datetime
                exp = datetime.strptime(product["expires"], "%Y-%m-%d")
                diff = (exp - today).days  # الفرق بين تاريخ اليوم وتاريخ الانتهاء
                
                # تصنيف المنتج بناءً على تاريخ الانتهاء
                if diff < 0:
                    product["status"] = "expired"  # المنتج انتهت صلاحيتها
                    alerts["expired"].append(product)
                elif diff <= 30:
                    product["status"] = "soon"  # المنتج سينتهي قريبًا
                    alerts["soon"].append(product)
                else:
                    product["status"] = "ok"  # المنتج صالح
                    alerts["ok"].append(product)
            except Exception as e:
                print(f"Error processing expiration date for product {product['name']}: {e}")
                continue  # إذا فشل في معالجة تاريخ الانتهاء، يتم تجاهل هذا المنتج

    return jsonify(alerts)  # إرجاع البيانات على شكل JSON

@app.route("/api/shopping")
def get_shopping_cart():
    return jsonify(read_cart())

@app.route("/api/shopping/add", methods=["POST"])
def add_shopping_items():
    data = request.json
    items = data.get("items", [])
    add_to_cart(items)
    return jsonify({"status": "success", "added": items})


@app.route("/api/shopping/remove", methods=["POST"])
def remove_item():
    username = session.get("user")
    if not username:
        return jsonify({"status": "error", "message": "يجب تسجيل الدخول"}), 401

    data = request.json
    item_to_remove = data.get("item", "").strip().lower()

    user_cart_file = os.path.join(BASE_DIR, f"shopping_cart_{username}.txt")
    if not os.path.exists(user_cart_file):
        return jsonify({"status": "error", "message": "Shopping file not found"})

    with open(user_cart_file, "r") as f:
        items = f.read().strip().splitlines()

    removed = False
    new_items = []
    for i in items:
        if i.strip().lower() == item_to_remove and not removed:
            removed = True
            continue
        new_items.append(i)

    with open(user_cart_file, "w") as f:
        f.write("\n".join(new_items) + "\n")

    return jsonify({"status": "removed" if removed else "not found"})

@app.route("/scan_web")
def scan_web():
    return render_template("mobile_scan.html")
@app.route("/api/auto_add_product")
@app.route("/api/auto_add_product")
def auto_add_product():
    username = session.get("user")
    if not username:
        return jsonify({"success": False, "message": "يجب تسجيل الدخول."}), 401

    barcode = request.args.get("barcode", "").strip()
    if not barcode:
        return jsonify({"success": False, "message": "الباركود غير موجود."})

    product_info = get_product_info(barcode)
    if not product_info:
        return jsonify({"success": False, "message": "لم يتم العثور على المنتج."})

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

    with open(user_product_file, "a", encoding="utf-8") as f:
        f.write(f"Product Information:\n")
        f.write(f"Product Name: {product_info.get('product_name', 'Not available')}\n")
        f.write(f"Brand: {product_info.get('brands', 'Not available')}\n")
        f.write(f"Ingredients: {product_info.get('ingredients_text', 'Not available')}\n")
        f.write(f"Energy: {product_info.get('nutriments', {}).get('energy-kcal', 'Not available')} kcal\n")
        f.write(f"Expiration Date: \n")  # يُضاف لاحقًا
        f.write(f"Barcode: {barcode}\n")
        f.write("="*50 + "\n")

    return jsonify({"success": True})

@app.route("/scan_mobile_full")
def scan_mobile_full():
    return render_template("mobile_scan_full.html")
    if not os.path.exists(SHOPPING_FILE):
        return jsonify({"status": "error", "message": "file not found"})

    with open(SHOPPING_FILE, "r") as f:
        items = f.read().splitlines()

    removed = False
    new_items = []
    for i in items:
        if i.strip().lower() == item_to_remove and not removed:
            removed = True
            continue
        new_items.append(i)

    with open(SHOPPING_FILE, "w") as f:
        f.write("\n".join(new_items) + "\n")

    return jsonify({"status": "removed" if removed else "not found"})

@app.route("/api/recipes")
def get_local_recipes():
    import unicodedata

    def normalize(text):
        return unicodedata.normalize('NFKC', text.strip().lower())

    products = read_products()
    all_ingredients = []

    for p in products:
        ing = p.get("ingredients", "")
        name = p.get("name", "")
        if ing:
            all_ingredients += [normalize(i) for i in ing.split(",") if i.strip()]
        elif name:
            all_ingredients.append(normalize(name))

    available = set(all_ingredients)
    suggestions = []

    for recipe in read_recipes():
        needed = set(normalize(i) for i in recipe["ingredients"])
        missing = list(needed - available)
        match_level = len(needed) - len(missing)
        suggestions.append({
            "name": recipe["name"],
            "available": list(needed & available),
            "missing": missing,
            "match_percent": int((match_level / len(needed)) * 100)
        })

    valid = [r for r in suggestions if r["available"]]
    valid.sort(key=lambda x: -x["match_percent"])
    return jsonify(valid)


@app.route("/api/recipes/online")
def get_online_recipes():
    products = read_products()
    all_ingredients = []
    for p in products:
        if "ingredients" in p and p["ingredients"].lower() != "not available":
            all_ingredients += [i.strip().lower() for i in p["ingredients"].split(",")]
    available = set(all_ingredients)
    category_url = "https://www.themealdb.com/api/json/v1/1/filter.php?c=Beef"
    response = requests.get(category_url)
    if response.status_code != 200:
        return jsonify([]) 
    meals = response.json().get("meals", [])[:10]
    suggestions = []
    for meal in meals:
        detail_res = requests.get(f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal['idMeal']}")
        meal_data = detail_res.json().get("meals", [])[0]
        ingredients = []
        for i in range(1, 21):
            ing = meal_data.get(f"strIngredient{i}")
            if ing and ing.strip():
                ingredients.append(ing.strip().lower())
        match = list(set(ingredients) & available)
        missing = list(set(ingredients) - available)
        if match:
            suggestions.append({
                "name": meal_data["strMeal"],
                "thumbnail": meal_data["strMealThumb"],
                "instructions": meal_data["strInstructions"],
                "source": meal_data.get("strSource") or f"https://www.themealdb.com/meal/{meal['idMeal']}",
                "available": match,
                "missing": missing
            })
    return jsonify(suggestions)

# مسار لعرض نموذج إضافة منتج

@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    username = session.get("user")
    if not username:
        return redirect(url_for("login"))

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

    if request.method == "POST":
        # الحصول على بيانات المنتج من النموذج
        product_name = request.form["productName"]
        brand = request.form["brand"]
        ingredients = request.form["ingredients"]
        energy = request.form["energy"]
        expiration_date = request.form["expirationDate"]
        barcode = request.form["barcode"]

        if not expiration_date:
            expiration_date = "غير متوفر"

        # حفظ المنتج في ملف المستخدم
        with open(user_product_file, "a", encoding="utf-8") as file:
            file.write(f"Product Information:\n")
            file.write(f"Product Name: {product_name}\n")
            file.write(f"Brand: {brand}\n")
            file.write(f"Ingredients: {ingredients}\n")
            file.write(f"Energy: {energy}\n")
            file.write(f"Expiration Date: {expiration_date}\n")
            file.write(f"Barcode: {barcode}\n")
            file.write("="*50 + "\n")

        return redirect(url_for("inventory"))

    return render_template("add_product.html")


@app.route("/enter_expiration_date")
def enter_expiration_date():
    barcode = request.args.get('barcode')
    return render_template("enter_expiration_date.html", barcode=barcode)

@app.route("/save_product_expiration", methods=["POST"])
@app.route("/save_product_expiration", methods=["POST"])
def save_product_expiration():
    username = session.get("user")
    if not username:
        return redirect(url_for("login"))

    user_product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

    barcode = request.form["barcode"]
    expiration_date = request.form["expirationDate"]

    if not expiration_date:
        return "تاريخ الانتهاء مطلوب ولا يمكن أن يكون فارغًا."

    product_info = get_product_info(barcode)
    if product_info:
        product_info["expiration_date"] = expiration_date

        with open(user_product_file, "a", encoding="utf-8") as f:
            f.write(f"Product Information:\n")
            f.write(f"Product Name: {product_info.get('product_name', 'Not available')}\n")
            f.write(f"Brand: {product_info.get('brands', 'Not available')}\n")
            f.write(f"Ingredients: {product_info.get('ingredients_text', 'Not available')}\n")
            f.write(f"Energy: {product_info.get('nutriments', {}).get('energy-kcal', 'Not available')} kcal\n")
            f.write(f"Expiration Date: {expiration_date}\n")
            f.write(f"Barcode: {barcode}\n")
            f.write("="*50 + "\n")

        return redirect(url_for("inventory"))
    else:
        return render_template("product_not_found.html", barcode=barcode, message="المنتج غير موجود أو لم يتم التعرف عليه.")

# مسار لبدء المسح وإدخال المنتجات
@app.route("/start_scan")
def start_scan():
    result = scan.start_scan()  # استدعاء دالة المسح من scan.py
    return result  # إرجاع النتيجة للمستخدم
from collections import Counter

@app.route("/statistics")
def statistics_page():
    return render_template("statistics.html")

@app.route("/api/stats_data")
def stats_data():
    username = session.get("user")
    if not username:
        return jsonify({"error": "يجب تسجيل الدخول"}), 401

    usage_file = os.path.join(BASE_DIR, f"usage_log_{username}.txt")
    product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

    today = datetime.today()
    week_ago = today - timedelta(days=7)
    used_this_week = 0
    top_product = ""
    usage_days = {}
    product_usage = []

    if os.path.exists(usage_file):
        with open(usage_file, "r", encoding="utf-8") as f:
            blocks = f.read().strip().split("="*40)
            for block in blocks:
                lines = block.strip().splitlines()
                entry = {line.split(":")[0].strip().lower(): line.split(":")[1].strip() for line in lines if ":" in line}
                if 'date' in entry and 'name' in entry:
                    try:
                        used_date = datetime.strptime(entry['date'], "%Y-%m-%d")
                        product_usage.append(entry['name'])
                        if used_date >= week_ago:
                            used_this_week += 1
                            key = used_date.strftime('%A')
                            usage_days[key] = usage_days.get(key, 0) + 1
                    except:
                        continue

    most_common = Counter(product_usage).most_common(1)
    if most_common:
        top_product = most_common[0][0]

    wasted_total = 0
    if os.path.exists(product_file):
        with open(product_file, "r", encoding="utf-8") as f:
            content = f.read().strip().split("=" * 50)
            for block in content:
                lines = block.strip().splitlines()
                for line in lines:
                    if "Expiration Date" in line:
                        try:
                            date_str = line.split(":", 1)[1].strip()
                            exp = datetime.strptime(date_str, "%Y-%m-%d")
                            if exp < today:
                                wasted_total += 1
                        except:
                            continue

    labels = list(usage_days.keys())
    values = list(usage_days.values())

    return jsonify({
        "used_total": used_this_week,
        "top_product": top_product,
        "wasted_total": wasted_total,
        "usage_chart": {"labels": labels, "values": values}
    })
@app.route("/users_board")
def users_board():
    return render_template("users_board.html")


@app.route("/api/users_board_data")
def users_board_data():
    users = load_users()
    today = datetime.today().strftime("%Y-%m-%d")
    results = []

    for username in users:
        usage_file = os.path.join(BASE_DIR, f"usage_log_{username}.txt")
        product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")

        used_total = used_today = 0
        top_product = ""
        used_names = []

        if os.path.exists(usage_file):
            with open(usage_file, "r", encoding="utf-8") as f:
                blocks = f.read().strip().split("="*40)
                for block in blocks:
                    lines = block.strip().splitlines()
                    entry = {line.split(":")[0].strip().lower(): line.split(":")[1].strip() for line in lines if ":" in line}
                    if 'date' in entry and 'name' in entry:
                        used_total += 1
                        used_names.append(entry['name'])
                        if entry['date'] == today:
                            used_today += 1

        if used_names:
            top_product = Counter(used_names).most_common(1)[0][0]

        wasted_total = 0
        if os.path.exists(product_file):
            with open(product_file, "r", encoding="utf-8") as f:
                content = f.read().strip().split("=" * 50)
                for block in content:
                    lines = block.strip().splitlines()
                    for line in lines:
                        if "Expiration Date" in line:
                            try:
                                date_str = line.split(":", 1)[1].strip()
                                exp = datetime.strptime(date_str, "%Y-%m-%d")
                                if exp < datetime.today():
                                    wasted_total += 1
                            except:
                                continue

        percent = f"{round((wasted_total / used_total) * 100)}%" if used_total else "0%"

        results.append({
            "user": username,
            "used_total": used_total,
            "used_today": used_today,
            "top_product": top_product,
            "wasted": wasted_total,
            "percent": percent
        })

    results.sort(key=lambda x: x["used_total"], reverse=True)
    return jsonify(results)
@app.route("/api/clean_fridge", methods=["POST"])
def clean_fridge():
    username = session.get("user")
    if not username:
        return jsonify({"success": False, "message": "يجب تسجيل الدخول"}), 401

    usage_file = os.path.join(BASE_DIR, f"usage_log_{username}.txt")

    with open(usage_file, "a", encoding="utf-8") as log:
        log.write(f"Name: CLEANING\n")
        log.write(f"Used: fridge cleaning\n")
        log.write(f"Date: {datetime.today().strftime('%Y-%m-%d')}\n")
        log.write("="*40 + "\n")

    return jsonify({"success": True, "message": "تم تسجيل عملية التنظيف ✅"})
@app.route("/api/users_stats")
def users_stats():
    from collections import Counter

    stats = []
    today = datetime.today()
    users = load_users()

    for username in users:
        product_file = os.path.join(BASE_DIR, f"product_info_{username}.txt")
        usage_file = os.path.join(BASE_DIR, f"usage_log_{username}.txt")

        total_products = 0
        expired = 0
        used = []
        total_calories = 0.0
        cleanings = 0

        if os.path.exists(product_file):
            with open(product_file, "r", encoding="utf-8") as f:
                blocks = f.read().strip().split("="*50)
                for block in blocks:
                    lines = block.strip().splitlines()
                    product_data = {}
                    for line in lines:
                        if ":" in line:
                            key, val = line.split(":", 1)
                            key = key.strip().lower()
                            val = val.strip()
                            product_data[key] = val

                    if "expiration date" in product_data:
                        try:
                            exp = datetime.strptime(product_data["expiration date"], "%Y-%m-%d")
                            if exp < today:
                                expired += 1
                        except:
                            pass

                    if "energy" in product_data and product_data["energy"].replace('.', '', 1).isdigit():
                        total_calories += float(product_data["energy"])

                    if product_data:
                        total_products += 1

        if os.path.exists(usage_file):
            with open(usage_file, "r", encoding="utf-8") as f:
                blocks = f.read().strip().split("="*40)
                for block in blocks:
                    lines = block.strip().splitlines()
                    for line in lines:
                        if line.lower().startswith("name:"):
                            used.append(line.split(":",1)[1].strip())
                        if line.lower().startswith("used:") and "clean" in line.lower():
                            cleanings += 1

        top_used = Counter(used).most_common(1)
        stats.append({
            "username": username,
            "total_products": total_products,
            "expired": expired,
            "top_used": top_used[0][0] if top_used else None,
            "total_calories": round(total_calories, 2),
            "login_count": users[username].get("visits", 0),
            "cleanings": cleanings,
            "online": users[username].get("online", False)
        })

    return jsonify({
        "users": stats,
        "total_users": len(users),
        "current_user_role": session.get("role")
    })

@app.route("/post/<post_id>/delete", methods=["POST"])
def delete_post(post_id):
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    role = session.get("role", "user")

    posts = load_posts()
    new_posts = []
    found = False

    for post in posts:
        if post["id"] == post_id:
            if post["username"] == username or role == "admin":
                found = True
                continue  # حذف هذا المنشور
        new_posts.append(post)

    if found:
        save_posts(new_posts)
        return redirect(url_for("view_posts"))
    else:
        return "❌ لا تملك صلاحية الحذف أو المنشور غير موجود", 403
    
if __name__ == "__main__":
    app.run(debug=True)
