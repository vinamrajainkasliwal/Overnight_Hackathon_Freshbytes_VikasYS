from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
from datetime import datetime
from uuid import uuid4
import math
import hashlib

app = Flask(__name__)
app.secret_key = "demo-secret-key-farm-ai"  # for sessions

DATA_DIR = "data"
FARMERS_FILE = os.path.join(DATA_DIR, "farmers.json")
ENTITLE_RULES_FILE = os.path.join(DATA_DIR, "entitlement_rules.json")
DEALERS_FILE = os.path.join(DATA_DIR, "dealers.json")
TXNS_FILE = os.path.join(DATA_DIR, "transactions.json")
FLAGGED_FILE = os.path.join(DATA_DIR, "flagged_cases.json")
IMAGE_HASHES_FILE = os.path.join(DATA_DIR, "image_hashes.json")

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---- Available languages for dropdown ----
LANGUAGES = [
    ("en", "English"),
    ("hi", "हिंदी"),
    ("ta", "தமிழ்"),
    ("kn", "ಕನ್ನಡ"),
    ("te", "తెలుగు"),
    ("bn", "বাংলা"),
    ("ml", "മലയാളം"),
    ("or", "ଓଡ଼ିଆ"),
]

# ---- Translation dictionary (you can expand later) ----
TRANSLATIONS = {
    "en": {
        "app_title": "E-Farmer Subsidy System",
        "nav_admin": "Admin Portal",
        "nav_dealer": "Dealer Portal",
        "nav_farmer": "Farmer Portal",
        "farmer_portal": "Farmer Portal",
        "image_status": "Image AI Status",
        "upload_images": "Upload Farm Images",
        "standard_photo": "Standard Land Photo",
        "corner_photo": "Corner / Left / Right Photo",
        "farmer_login_title": "Farmer Login",
        "farmer_login_button": "Login as Farmer",
        "login_efn_label": "E-Farmer Number (EFN)",
        "login_password_label": "Password",
        "login_hint": "Enter your E-Farmer Number (EFN) and password fam1."
    },
    "hi": {
        "app_title": "ई-फार्मर सब्सिडी सिस्टम",
        "nav_admin": "ऐडमिन पोर्टल",
        "nav_dealer": "डीलर पोर्टल",
        "nav_farmer": "किसान पोर्टल",
        "farmer_portal": "किसान पोर्टल",
        "image_status": "छवि AI स्थिति",
        "upload_images": "खेत की फोटो अपलोड करें",
        "standard_photo": "साधारण खेत की फोटो",
        "corner_photo": "कोने / बाएँ / दाएँ की फोटो",
        "farmer_login_title": "किसान लॉगिन",
        "farmer_login_button": "किसान के रूप में लॉगिन करें",
        "login_efn_label": "ई-फार्मर नंबर (EFN)",
        "login_password_label": "पासवर्ड",
        "login_hint": "अपना ई-फार्मर नंबर (EFN) और पासवर्ड fam1 दर्ज करें."
    },
    "ta": {
        "app_title": "இ-ஃபார்மர் சலுகை அமைப்பு",
        "nav_admin": "நிர்வாக போர்டல்",
        "nav_dealer": "டீலர் போர்டல்",
        "nav_farmer": "விவசாயி போர்டல்",
        "farmer_portal": "விவசாயி போர்டல்",
        "image_status": "பட AI நிலை",
        "upload_images": "பண்ணை படங்களை பதிவேற்றவும்",
        "standard_photo": "நிலத்தின் சாதாரண படம்",
        "corner_photo": "மூலை / இடது / வலது படம்",
        "farmer_login_title": "விவசாயி உள்நுழைவு",
        "farmer_login_button": "விவசாயியாக உள்நுழைக",
        "login_efn_label": "இ-ஃபார்மர் எண் (EFN)",
        "login_password_label": "கடவுச்சொல்",
        "login_hint": "உங்கள் இ-ஃபார்மர் எண் (EFN) மற்றும் கடவுச்சொல் fam1 ஐ உள்ளிடுங்கள்."
    }
    # you can add te/kn/ml/bn/or later if you want
}


def get_lang():
    """Reads ?lang=xx from URL and stores it in session."""
    code = request.args.get("lang")
    if code:
        session["lang"] = code
    return session.get("lang", "en")


@app.context_processor
def inject_globals():
    """Make languages, selected language & translation dict available in all templates."""
    code = session.get("lang", "en")
    t = TRANSLATIONS.get(code, TRANSLATIONS["en"])
    return {
        "languages": LANGUAGES,
        "current_lang": code,
        "t": t,
    }


# ---------- JSON helper functions ----------

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def compute_image_hash(path):
    """Return SHA256 hash of an image file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- Entitlement + Fraud Logic ----------

def get_entitlement_for_farmer(farmer, product="Urea"):
    rules = load_json(ENTITLE_RULES_FILE, [])
    crop = farmer.get("cropType")
    zone = farmer.get("rainfallZone")
    land_area = float(farmer.get("landArea", 0) or 0)

    for rule in rules:
        if (
            rule.get("cropType") == crop
            and rule.get("rainfallZone") == zone
            and rule.get("productType") == product
        ):
            max_per_acre = float(rule.get("maxPerAcre", 0))
            return land_area * max_per_acre
    return 0.0


def run_basic_fraud_checks(transaction, farmer):
    claimed_qty = float(transaction.get("quantity", 0) or 0)
    product = transaction.get("productType", "Urea")
    max_allowed = get_entitlement_for_farmer(farmer, product=product)

    if max_allowed <= 0:
        return False, "No entitlement rule defined"

    if claimed_qty > max_allowed:
        diff = claimed_qty - max_allowed
        reason = f"Quantity exceeds entitlement by {diff:.1f} units"
        return True, reason

    return False, "Within entitlement"


# ---------- AI-ish eligibility suggestion (rule-based) ----------

def compute_ai_eligibility(farmer):
    schemes = []

    land = float(farmer.get("landArea", 0) or 0)
    crop = (farmer.get("cropType") or "").lower()
    soil = (farmer.get("soilType") or "").lower()
    zone = (farmer.get("rainfallZone") or "").lower()

    if land <= 2.0:
        schemes.append({
            "name": "PM-KISAN (Small Farmer Income Support)",
            "reason": "Landholding ≤ 2 acres",
            "status": "Likely Eligible"
        })

    if zone == "low":
        schemes.append({
            "name": "Micro-Irrigation / Drip Subsidy",
            "reason": "Low rainfall zone",
            "status": "Recommended"
        })

    if "paddy" in crop or "wheat" in crop:
        schemes.append({
            "name": "Fertilizer & MSP Support Scheme",
            "reason": f"Staple crop detected ({farmer.get('cropType')})",
            "status": "Likely Eligible"
        })

    if "black" in soil or "red" in soil:
        schemes.append({
            "name": "Soil Health Card & Nutrient Management",
            "reason": f"Soil type: {farmer.get('soilType')}",
            "status": "Advisory"
        })

    if not schemes:
        schemes.append({
            "name": "No specific scheme matched",
            "reason": "Profile does not match current rule set",
            "status": "Needs Manual Review"
        })

    return schemes


# ---------- AUTH / LOGIN ROUTES ----------

# NOTE: per your request, all usernames & passwords are fam1/fam1 (for demo)

@app.route("/")
def index():
    get_lang()
    return render_template("base.html")


@app.route("/login/admin", methods=["GET", "POST"])
def login_admin():
    get_lang()
    error = None
    if request.method == "POST":
        if request.form.get("username") == "fam1" and request.form.get("password") == "fam1":
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))
        else:
            error = "Invalid admin credentials"
    return render_template("login.html", role="admin", error=error)


@app.route("/login/dealer", methods=["GET", "POST"])
def login_dealer():
    get_lang()
    error = None
    if request.method == "POST":
        if request.form.get("username") == "fam1" and request.form.get("password") == "fam1":
            session["role"] = "dealer"
            # optional: track which dealer they are using
            session["dealer_id"] = request.form.get("dealerId") or "D001"
            return redirect(url_for("dealer_portal"))
        else:
            error = "Invalid dealer credentials"
    dealers = load_json(DEALERS_FILE, [])
    return render_template("login.html", role="dealer", dealers=dealers, error=error)


@app.route("/login/farmer", methods=["GET", "POST"])
def login_farmer():
    get_lang()
    error = None
    if request.method == "POST":
        efn = request.form.get("efn")
        password = request.form.get("password")
        farmers = load_json(FARMERS_FILE, {})
        if password == "fam1" and efn in farmers:
            session["role"] = "farmer"
            session["efn"] = efn
            return redirect(url_for("farmer_home", efn=efn))
        else:
            error = "Invalid EFN or password"
    return render_template("login.html", role="farmer", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- FARMER REGISTRATION (ADMIN ONLY) ----------

@app.route("/register-farmer", methods=["GET", "POST"])
def register_farmer():
    get_lang()
    if session.get("role") != "admin":
        return redirect(url_for("login_admin"))

    if request.method == "POST":
        farmers = load_json(FARMERS_FILE, {})

        name = request.form.get("farmerName")
        aadhaar = request.form.get("aadhaar")
        ration = request.form.get("rationCard")
        phone = request.form.get("phone")
        village = request.form.get("village")
        district = request.form.get("district")
        land_area = request.form.get("landArea")
        soil_type = request.form.get("soilType")
        crop_type = request.form.get("cropType")
        rainfall_zone = request.form.get("rainfallZone")
        land_lat = request.form.get("landLat") or ""
        land_lon = request.form.get("landLon") or ""

        dist_code = (district or "IND").upper()[:3]
        efn = f"EFN-{dist_code}-{str(uuid4())[:8].upper()}"

        farmer = {
            "efn": efn,
            "farmerName": name,
            "aadhaar": aadhaar,
            "rationCard": ration,
            "phone": phone,
            "village": village,
            "district": district,
            "landArea": land_area,
            "soilType": soil_type,
            "cropType": crop_type,
            "rainfallZone": rainfall_zone,
            "landLat": land_lat,
            "landLon": land_lon,
            "imageStatus": "Images Pending"
        }

        farmers[efn] = farmer
        save_json(FARMERS_FILE, farmers)

        return render_template("register_farmer.html", farmer=farmer)

    return render_template("register_farmer.html", farmer=None)


# ---------- FARMER PORTAL + IMAGE UPLOAD ----------

@app.route("/farmer/<efn>", methods=["GET"])
def farmer_home(efn):
    get_lang()
    # allow direct view OR via farmer login
    farmers = load_json(FARMERS_FILE, {})
    farmer = farmers.get(efn)
    if not farmer:
        return f"No farmer found for EFN: {efn}", 404

    max_urea = get_entitlement_for_farmer(farmer, product="Urea")
    nearest_center = "RV Agro Cooperative Center, 4 km away (demo)"
    laws_link = "https://www.india.gov.in/topics/agriculture"
    ai_schemes = compute_ai_eligibility(farmer)

    return render_template(
        "farmer_home.html",
        farmer=farmer,
        max_urea=max_urea,
        nearest_center=nearest_center,
        laws_link=laws_link,
        ai_schemes=ai_schemes,
    )


@app.route("/farmer/<efn>/upload-images", methods=["POST"])
def upload_farmer_images(efn):
    get_lang()
    farmers = load_json(FARMERS_FILE, {})
    farmer = farmers.get(efn)
    if not farmer:
        return f"No farmer found for EFN: {efn}", 404

    std_img = request.files.get("standardImage")
    corner_img = request.files.get("cornerImage")

    # image_hashes = { hash_value: [ { "efn": "...", "imageType": "standard"/"corner" } ] }
    image_hashes = load_json(IMAGE_HASHES_FILE, {})
    suspicious_reasons = []

    # ---- handle standard image ----
    if std_img and std_img.filename:
        ext = os.path.splitext(std_img.filename)[1]
        fname = f"{efn}_base{ext}"
        path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
        std_img.save(path)
        farmer["standardImage"] = fname

        h = compute_image_hash(path)
        existing = image_hashes.get(h, [])

        # check if this image was used before
        for entry in existing:
            if entry["efn"] != efn:
                suspicious_reasons.append(
                    f"Standard image reused from EFN {entry['efn']} ({entry['imageType']})"
                )
            elif entry["efn"] == efn and entry["imageType"] != "standard":
                suspicious_reasons.append("Same image used for both standard and corner photos")

        # record this usage
        existing.append({"efn": efn, "imageType": "standard"})
        image_hashes[h] = existing

    # ---- handle corner image ----
    if corner_img and corner_img.filename:
        ext2 = os.path.splitext(corner_img.filename)[1]
        fname2 = f"{efn}_corner{ext2}"
        path2 = os.path.join(app.config["UPLOAD_FOLDER"], fname2)
        corner_img.save(path2)
        farmer["cornerImage"] = fname2

        h2 = compute_image_hash(path2)
        existing2 = image_hashes.get(h2, [])

        for entry in existing2:
            if entry["efn"] != efn:
                suspicious_reasons.append(
                    f"Corner image reused from EFN {entry['efn']} ({entry['imageType']})"
                )
            elif entry["efn"] == efn and entry["imageType"] != "corner":
                suspicious_reasons.append("Same image used for both standard and corner photos")

        existing2.append({"efn": efn, "imageType": "corner"})
        image_hashes[h2] = existing2

    # decide final status
    if suspicious_reasons:
        farmer["imageStatus"] = "Suspicious: " + " | ".join(suspicious_reasons)
    elif farmer.get("standardImage") and farmer.get("cornerImage"):
        farmer["imageStatus"] = "Verified (unique images)"
    else:
        farmer["imageStatus"] = "Images Pending"

    # save back
    farmers[efn] = farmer
    save_json(FARMERS_FILE, farmers)
    save_json(IMAGE_HASHES_FILE, image_hashes)

    return redirect(url_for("farmer_home", efn=efn))


# ---------- DEALER PORTAL (LOGIN REQUIRED) ----------

@app.route("/dealer", methods=["GET", "POST"])
def dealer_portal():
    get_lang()
    if session.get("role") != "dealer":
        return redirect(url_for("login_dealer"))

    dealers = load_json(DEALERS_FILE, [])
    farmers = load_json(FARMERS_FILE, {})

    message = None
    txn_code = None
    risk_info = None
    farmer_preview = None

    if request.method == "POST":
        efn = request.form.get("efn")
        dealer_id = request.form.get("dealerId")
        product_type = request.form.get("productType")
        quantity = request.form.get("quantity")
        unit = request.form.get("unit")
        date_str = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")

        farmer = farmers.get(efn)
        if not farmer:
            message = f"No farmer found for EFN: {efn}"
        else:
            txns = load_json(TXNS_FILE, [])
            txn_code = f"TXN-{datetime.now().strftime('%Y%m%d')}-{str(uuid4())[:6].upper()}"
            txn = {
                "transactionId": txn_code,
                "efn": efn,
                "dealerId": dealer_id,
                "productType": product_type,
                "quantity": quantity,
                "unit": unit,
                "date": date_str,
                "createdAt": datetime.now().isoformat()
            }
            txns.append(txn)
            save_json(TXNS_FILE, txns)

            suspicious, reason = run_basic_fraud_checks(txn, farmer)
            if suspicious:
                flagged = load_json(FLAGGED_FILE, [])
                case_id = f"CASE-{str(uuid4())[:8].upper()}"
                flagged_case = {
                    "caseId": case_id,
                    "transactionId": txn_code,
                    "efn": efn,
                    "dealerId": dealer_id,
                    "reason": reason,
                    "severity": "High",
                    "timestamp": datetime.now().isoformat()
                }
                flagged.append(flagged_case)
                save_json(FLAGGED_FILE, flagged)

                risk_info = {"status": "Suspicious", "reason": reason}
                message = "Transaction recorded but flagged as suspicious."
            else:
                risk_info = {"status": "OK", "reason": reason}
                message = "Transaction recorded successfully."

            farmer_preview = farmer

    return render_template(
        "dealer.html",
        dealers=dealers,
        message=message,
        txn_code=txn_code,
        risk_info=risk_info,
        farmer_preview=farmer_preview,
    )


# ---------- ADMIN DASHBOARD (FARMER TABLE + SEARCH) ----------

@app.route("/admin")
def admin_dashboard():
    get_lang()
    if session.get("role") != "admin":
        return redirect(url_for("login_admin"))

    farmers = load_json(FARMERS_FILE, {})
    farmer_list = list(farmers.values())
    txns = load_json(TXNS_FILE, [])
    flagged = load_json(FLAGGED_FILE, [])

    total_farmers = len(farmers)
    total_txns = len(txns)
    total_flagged = len(flagged)

    dealer_counts = {}
    for t in txns:
        did = t.get("dealerId")
        dealer_counts[did] = dealer_counts.get(did, 0) + 1

    return render_template(
        "admin.html",
        total_farmers=total_farmers,
        total_txns=total_txns,
        total_flagged=total_flagged,
        dealer_counts=dealer_counts,
        flagged_cases=flagged,
        farmers=farmer_list,
    )


if __name__ == "__main__":
    app.run(debug=True)
