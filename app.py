import hmac
import json
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import bcrypt
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
logging.basicConfig(level=logging.INFO)

ENTITY_CONFIG = {
    "tours": {
        "title": "Аялал",
        "singular": "аялал",
        "table": "tours",
        "select": "id,name,destination,description,duration_days,price,created_at",
        "search_columns": ("name", "destination"),
        "fields": (
            {"name": "name", "label": "Аяллын нэр", "type": "text"},
            {"name": "destination", "label": "Чиглэл", "type": "text"},
            {"name": "description", "label": "Тайлбар", "type": "textarea"},
            {"name": "duration_days", "label": "Хоног", "type": "number", "min": "1", "step": "1"},
            {"name": "price", "label": "Үнэ (₮)", "type": "number", "min": "0", "step": "0.01"},
        ),
        "columns": (
            {"name": "name", "label": "Аяллын нэр"},
            {"name": "destination", "label": "Чиглэл"},
            {"name": "duration_days", "label": "Хоног"},
            {"name": "price", "label": "Үнэ"},
        ),
    },
    "staff": {
        "title": "Ажилтан",
        "singular": "ажилтан",
        "table": "staff",
        "select": "id,full_name,email,phone,role,created_at",
        "search_columns": ("full_name", "email", "role"),
        "fields": (
            {"name": "full_name", "label": "Овог, нэр", "type": "text"},
            {"name": "email", "label": "И-мэйл", "type": "email"},
            {"name": "phone", "label": "Утас", "type": "tel"},
            {"name": "role", "label": "Албан тушаал", "type": "text"},
        ),
        "columns": (
            {"name": "full_name", "label": "Овог, нэр"},
            {"name": "email", "label": "И-мэйл"},
            {"name": "phone", "label": "Утас"},
            {"name": "role", "label": "Албан тушаал"},
        ),
    },
}


class SupabaseError(Exception):
    pass


def supabase_select(table, params):
    if not SUPABASE_URL:
        raise SupabaseError("SUPABASE_URL is not set")
    if not (SUPABASE_KEY.startswith("sb_secret_") or SUPABASE_KEY.startswith("eyJ")):
        raise SupabaseError(
            "SUPABASE_SECRET_KEY must be a Supabase secret key (sb_secret_...) "
            "or a legacy service_role key"
        )

    query = urlencode(params)
    endpoint = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    headers = {"apikey": SUPABASE_KEY, "Accept": "application/json"}
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    req = Request(endpoint, headers=headers)
    try:
        with urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logging.error("Supabase request to %s failed with HTTP %s", table, exc.code)
        raise SupabaseError(f"Supabase request failed (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logging.error("Supabase request to %s failed: %s", table, exc)
        raise SupabaseError("Could not reach Supabase or read its response") from exc

    if not isinstance(data, list):
        raise SupabaseError("Supabase returned an unexpected response")
    return data


def supabase_update(table, params, values):
    if not SUPABASE_URL:
        raise SupabaseError("SUPABASE_URL is not set")
    if not (SUPABASE_KEY.startswith("sb_secret_") or SUPABASE_KEY.startswith("eyJ")):
        raise SupabaseError(
            "SUPABASE_SECRET_KEY must be a Supabase secret key (sb_secret_...) "
            "or a legacy service_role key"
        )

    endpoint = f"{SUPABASE_URL}/rest/v1/{table}?{urlencode(params)}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    req = Request(
        endpoint,
        data=json.dumps(values).encode("utf-8"),
        headers=headers,
        method="PATCH",
    )
    try:
        with urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logging.error("Supabase update to %s failed with HTTP %s", table, exc.code)
        raise SupabaseError(f"Supabase update failed (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logging.error("Supabase update to %s failed: %s", table, exc)
        raise SupabaseError("Could not reach Supabase or read its response") from exc

    if not isinstance(data, list):
        raise SupabaseError("Supabase returned an unexpected update response")
    return data


def supabase_insert(table, values):
    if not SUPABASE_URL:
        raise SupabaseError("SUPABASE_URL is not set")
    if not (SUPABASE_KEY.startswith("sb_secret_") or SUPABASE_KEY.startswith("eyJ")):
        raise SupabaseError("A Supabase secret key is required for server-side changes")

    headers = {
        "apikey": SUPABASE_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    req = Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(values).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logging.error("Supabase insert to %s failed with HTTP %s", table, exc.code)
        raise SupabaseError(f"Supabase insert failed (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logging.error("Supabase insert to %s failed: %s", table, exc)
        raise SupabaseError("Could not reach Supabase or read its response") from exc

    if not isinstance(data, list):
        raise SupabaseError("Supabase returned an unexpected insert response")
    return data


def supabase_delete(table, params):
    if not SUPABASE_URL:
        raise SupabaseError("SUPABASE_URL is not set")
    if not (SUPABASE_KEY.startswith("sb_secret_") or SUPABASE_KEY.startswith("eyJ")):
        raise SupabaseError("A Supabase secret key is required for server-side changes")

    headers = {
        "apikey": SUPABASE_KEY,
        "Accept": "application/json",
        "Prefer": "return=representation",
    }
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    req = Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{urlencode(params)}",
        headers=headers,
        method="DELETE",
    )
    try:
        with urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else []
    except HTTPError as exc:
        logging.error("Supabase delete from %s failed with HTTP %s", table, exc.code)
        raise SupabaseError(f"Supabase delete failed (HTTP {exc.code})") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logging.error("Supabase delete from %s failed: %s", table, exc)
        raise SupabaseError("Could not reach Supabase or read its response") from exc

    if not isinstance(data, list):
        raise SupabaseError("Supabase returned an unexpected delete response")
    return data


def get_entity_config(entity):
    config = ENTITY_CONFIG.get(entity)
    if config is None:
        abort(404)
    return config


def validate_entity_form(config):
    values = {}
    errors = []
    for field in config["fields"]:
        name = field["name"]
        value = request.form.get(name, "").strip()
        if not value:
            errors.append(f"{field['label']} талбарыг бөглөнө үү.")
            continue
        if name == "duration_days":
            try:
                days = int(value)
            except ValueError:
                errors.append("Хоногийг бүхэл тоогоор оруулна уу.")
                continue
            if days < 1:
                errors.append("Хоног 1-ээс багагүй байна.")
                continue
            values[name] = days
        elif name == "price":
            try:
                price = Decimal(value)
            except InvalidOperation:
                errors.append("Үнийг зөв тоогоор оруулна уу.")
                continue
            if not price.is_finite() or price < 0 or price > Decimal("9999999999.99"):
                errors.append("Үнэ 0-ээс багагүй, 9,999,999,999.99-ээс ихгүй байна.")
                continue
            if price.as_tuple().exponent < -2:
                errors.append("Үнийн бутархай хэсэг 2 орноос ихгүй байна.")
                continue
            values[name] = format(price, "f")
        else:
            if name == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                errors.append("И-мэйл хаягаа зөв оруулна уу.")
                continue
            values[name] = value
    return values, errors


def search_filter(term, columns):
    escaped = term.replace("\\", "\\\\")
    for character in (",", "(", ")", '"'):
        escaped = escaped.replace(character, f"\\{character}")
    conditions = ",".join(f"{column}.ilike.*{escaped}*" for column in columns)
    return f"({conditions})"


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


@app.get("/")
def home():
    if session.get("user_email"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_email"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
            abort(400)

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            flash("И-мэйл болон нууц үгээ оруулна уу.")
            return render_template("login.html", csrf_token=csrf_token())

        try:
            users = supabase_select(
                "users",
                {"select": "email,password_hash", "email": f"eq.{email}", "limit": "1"},
            )
        except SupabaseError as exc:
            logging.error("Login could not query Supabase: %s", exc)
            flash("Supabase холболтыг шалгана уу. Түлхүүр буруу эсвэл холболт амжилтгүй байна.")
            return render_template("login.html", csrf_token=csrf_token()), 503

        if users:
            user = users[0]
            try:
                password_valid = bcrypt.checkpw(
                    password.encode("utf-8"),
                    user["password_hash"].encode("utf-8"),
                )
            except (KeyError, ValueError, TypeError):
                logging.error("Invalid password hash for user record")
                password_valid = False
            if password_valid:
                session.clear()
                session["user_email"] = user["email"]
                csrf_token()
                return redirect(url_for("dashboard"))

        flash("И-мэйл эсвэл нууц үг буруу байна.")

    return render_template("login.html", csrf_token=csrf_token())


@app.get("/dashboard")
def dashboard():
    if not session.get("user_email"):
        return redirect(url_for("login"))

    try:
        drafts = supabase_select(
            "content_drafts",
            {"select": "id,title,content,status,created_at", "order": "created_at.desc"},
        )
    except SupabaseError as exc:
        logging.error("Could not load content drafts: %s", exc)
        flash("Ноорог постуудыг ачаалж чадсангүй. Supabase холболтоо шалгана уу.")
        return render_template(
            "dashboard.html",
            drafts=[],
            email=session["user_email"],
            csrf_token=csrf_token(),
            load_error=True,
            active_section="content",
        ), 503

    return render_template(
        "dashboard.html",
        drafts=drafts,
        email=session["user_email"],
        csrf_token=csrf_token(),
        load_error=False,
        active_section="content",
    )


@app.post("/drafts/<uuid:draft_id>/<action>")
def update_draft_status(draft_id, action):
    if not session.get("user_email"):
        return redirect(url_for("login"))
    if not hmac.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
        abort(400)

    new_status = {"approve": "approved", "reject": "rejected"}.get(action)
    if new_status is None:
        abort(404)

    try:
        updated = supabase_update(
            "content_drafts",
            {"id": f"eq.{draft_id}", "status": "in.(draft,pending)"},
            {"status": new_status},
        )
    except SupabaseError as exc:
        logging.error("Could not update draft status: %s", exc)
        flash("Нооргийн төлөвийг өөрчилж чадсангүй. Дахин оролдоно уу.")
        return redirect(url_for("dashboard"))

    if not updated:
        flash("Ноорог олдсонгүй эсвэл хүлээгдэж буй төлөвт байхаа больсон байна.")
        return redirect(url_for("dashboard"))

    flash("Нооргийг баталлаа." if new_status == "approved" else "Нооргоос татгалзлаа.")
    return redirect(url_for("dashboard"))


@app.get("/facebook")
def facebook():
    if not session.get("user_email"):
        return redirect(url_for("login"))
    return render_template(
        "coming_soon.html",
        email=session["user_email"],
        csrf_token=csrf_token(),
        active_section="facebook",
        section_title="Facebook",
    )


@app.get("/chat")
def chat():
    if not session.get("user_email"):
        return redirect(url_for("login"))
    return render_template(
        "coming_soon.html",
        email=session["user_email"],
        csrf_token=csrf_token(),
        active_section="chat",
        section_title="Чат",
    )


@app.get("/bookings")
def bookings():
    if not session.get("user_email"):
        return redirect(url_for("login"))

    try:
        rows = supabase_select(
            "bookings",
            {
                "select": "id,customer_name,customer_email,service_name,starts_at,status",
                "order": "starts_at.asc",
            },
        )
    except SupabaseError as exc:
        logging.error("Could not load bookings: %s", exc)
        flash("Захиалгуудыг ачаалж чадсангүй. Supabase холболтоо шалгана уу.")
        return render_template(
            "bookings.html",
            bookings=[],
            email=session["user_email"],
            csrf_token=csrf_token(),
            load_error=True,
            active_section="bookings",
        ), 503

    return render_template(
        "bookings.html",
        bookings=rows,
        email=session["user_email"],
        csrf_token=csrf_token(),
        load_error=False,
        active_section="bookings",
    )


@app.get("/<entity>")
def entity_list(entity):
    config = get_entity_config(entity)
    if not session.get("user_email"):
        return redirect(url_for("login"))

    term = request.args.get("q", "").strip()
    params = {"select": config["select"], "order": "created_at.desc"}
    if term:
        params["or"] = search_filter(term, config["search_columns"])
    try:
        rows = supabase_select(config["table"], params)
    except SupabaseError as exc:
        logging.error("Could not load %s: %s", config["table"], exc)
        flash(f"{config['title']} мэдээллийг ачаалж чадсангүй.")
        return render_template(
            "entity_list.html",
            entity=entity,
            config=config,
            rows=[],
            term=term,
            email=session["user_email"],
            csrf_token=csrf_token(),
            active_section=entity,
            load_error=True,
        ), 503

    return render_template(
        "entity_list.html",
        entity=entity,
        config=config,
        rows=rows,
        term=term,
        email=session["user_email"],
        csrf_token=csrf_token(),
        active_section=entity,
        load_error=False,
    )


@app.route("/<entity>/new", methods=["GET", "POST"])
def entity_new(entity):
    config = get_entity_config(entity)
    if not session.get("user_email"):
        return redirect(url_for("login"))

    values = {}
    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
            abort(400)
        values, errors = validate_entity_form(config)
        if errors:
            for error in errors:
                flash(error)
        else:
            values.update(
                id=str(uuid.uuid4()),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            try:
                created = supabase_insert(config["table"], values)
            except SupabaseError as exc:
                logging.error("Could not create %s record: %s", config["table"], exc)
                flash("Мэдээллийг хадгалж чадсангүй. Хүснэгт болон Supabase холболтоо шалгана уу.")
            else:
                if created:
                    flash(f"{config['singular'].capitalize()} нэмлээ.")
                    return redirect(url_for("entity_list", entity=entity))
                flash("Мэдээлэл хадгалагдсан эсэхийг баталгаажуулж чадсангүй.")

    return render_template(
        "entity_form.html",
        entity=entity,
        config=config,
        values=values,
        email=session["user_email"],
        csrf_token=csrf_token(),
        active_section=entity,
        page_title=f"{config['title']} нэмэх",
    )


@app.route("/<entity>/<uuid:item_id>/edit", methods=["GET", "POST"])
def entity_edit(entity, item_id):
    config = get_entity_config(entity)
    if not session.get("user_email"):
        return redirect(url_for("login"))

    if request.method == "POST":
        if not hmac.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
            abort(400)
        values, errors = validate_entity_form(config)
        if errors:
            for error in errors:
                flash(error)
        else:
            try:
                updated = supabase_update(
                    config["table"],
                    {"id": f"eq.{item_id}"},
                    values,
                )
            except SupabaseError as exc:
                logging.error("Could not update %s record: %s", config["table"], exc)
                flash("Өөрчлөлтийг хадгалж чадсангүй. Дахин оролдоно уу.")
            else:
                if updated:
                    flash(f"{config['singular'].capitalize()} мэдээллийг шинэчиллээ.")
                    return redirect(url_for("entity_list", entity=entity))
                flash("Засах мэдээлэл олдсонгүй.")
                return redirect(url_for("entity_list", entity=entity))
    else:
        try:
            records = supabase_select(
                config["table"],
                {"select": config["select"], "id": f"eq.{item_id}", "limit": "1"},
            )
        except SupabaseError as exc:
            logging.error("Could not load %s record: %s", config["table"], exc)
            flash("Засах мэдээллийг ачаалж чадсангүй.")
            return redirect(url_for("entity_list", entity=entity))
        if not records:
            flash("Засах мэдээлэл олдсонгүй.")
            return redirect(url_for("entity_list", entity=entity))
        values = records[0]

    return render_template(
        "entity_form.html",
        entity=entity,
        config=config,
        values=values,
        email=session["user_email"],
        csrf_token=csrf_token(),
        active_section=entity,
        page_title=f"{config['title']} засах",
    )


@app.post("/<entity>/<uuid:item_id>/delete")
def entity_delete(entity, item_id):
    config = get_entity_config(entity)
    if not session.get("user_email"):
        return redirect(url_for("login"))
    if not hmac.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
        abort(400)

    confirmation_key = f"{entity}:{item_id}"
    confirmation = request.form.get("confirm")
    if confirmation == "no":
        if session.get("pending_delete") == confirmation_key:
            session.pop("pending_delete")
        return redirect(url_for("entity_list", entity=entity))

    if confirmation != "yes":
        try:
            records = supabase_select(
                config["table"],
                {"select": config["select"], "id": f"eq.{item_id}", "limit": "1"},
            )
        except SupabaseError as exc:
            logging.error("Could not load %s for deletion: %s", config["table"], exc)
            flash("Устгах мэдээллийг ачаалж чадсангүй.")
            return redirect(url_for("entity_list", entity=entity))
        if not records:
            flash("Устгах мэдээлэл олдсонгүй.")
            return redirect(url_for("entity_list", entity=entity))
        session["pending_delete"] = confirmation_key
        return render_template(
            "confirm_delete.html",
            entity=entity,
            config=config,
            item=records[0],
            email=session["user_email"],
            csrf_token=csrf_token(),
            active_section=entity,
        )

    if session.get("pending_delete") != confirmation_key:
        abort(400)
    session.pop("pending_delete")
    try:
        deleted = supabase_delete(config["table"], {"id": f"eq.{item_id}"})
    except SupabaseError as exc:
        logging.error("Could not delete %s record: %s", config["table"], exc)
        flash("Устгаж чадсангүй. Дахин оролдоно уу.")
    else:
        if deleted:
            flash(f"{config['singular'].capitalize()} устгалаа.")
        else:
            flash("Устгах мэдээлэл олдсонгүй.")
    return redirect(url_for("entity_list", entity=entity))


@app.post("/logout")
def logout():
    if not hmac.compare_digest(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
        abort(400)
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
