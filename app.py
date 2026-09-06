import os
import math
import unicodedata
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    session,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import db, User, Message, Photo, Projet

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-moi-en-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    BASE_DIR, "instance", "nous_deux.db"
)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 Mo max par upload

# Mot de code pour débloquer l'app depuis la fausse page d'erreur
MOT_DE_CODE = os.environ.get("MOT_DE_CODE", "etoile")

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ROOM = "notre-room"  # room unique partagée par les deux utilisateurs


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.after_request
def interdire_indexation(response):
    """Empêche les moteurs de recherche d'indexer quoi que ce soit sur ce domaine."""
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
    return response


@app.route("/robots.txt")
def robots_txt():
    return app.send_static_file("robots.txt")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def normaliser(texte):
    """Retire les accents et met en minuscule, pour comparer sans piéger sur é/e."""
    texte = texte.strip().lower()
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Portail de camouflage — page vue par défaut, avant déverrouillage
# ---------------------------------------------------------------------------

ENDPOINTS_PUBLICS = {"portail", "static", "robots_txt"}


@app.before_request
def verifier_deverrouillage():
    if request.endpoint in ENDPOINTS_PUBLICS or request.endpoint is None:
        return
    if current_user.is_authenticated:
        return
    if session.get("deverrouille"):
        return
    return redirect(url_for("portail"))


@app.route("/", methods=["GET", "POST"])
def portail():
    if request.method == "POST":
        saisie = normaliser(request.form.get("champ", ""))
        if saisie == normaliser(MOT_DE_CODE):
            # Déverrouillage valable uniquement pour cette visite : on ne
            # persiste rien à long terme, le mot de code sera redemandé
            # à la prochaine ouverture de l'app.
            session["deverrouille"] = True
            if current_user.is_authenticated:
                return redirect(url_for("chat"))
            return redirect(url_for("login"))
        # Mauvaise saisie : on réaffiche la même fausse page d'erreur,
        # sans aucun indice supplémentaire.
        return render_template("portail.html"), 503

    # GET : on affiche systématiquement la fausse page, même si l'utilisateur
    # est déjà connecté ou avait déjà déverrouillé plus tôt dans la session.
    return render_template("portail.html"), 503


def haversine(lat1, lon1, lat2, lon2):
    """Distance en km entre deux points GPS (formule de Haversine)."""
    R = 6371.0  # rayon de la Terre en km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("chat"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return redirect(url_for("chat"))
        flash("Identifiants incorrects.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Pages principales
# ---------------------------------------------------------------------------


@app.route("/chat")
@login_required
def chat():
    messages = Message.query.order_by(Message.timestamp.asc()).limit(200).all()
    autre = User.query.filter(User.id != current_user.id).first()
    return render_template("chat.html", messages=messages, autre=autre)


@app.route("/galerie")
@login_required
def galerie():
    photos = Photo.query.order_by(Photo.timestamp.desc()).all()
    return render_template("galerie.html", photos=photos)


@app.route("/galerie/upload", methods=["POST"])
@login_required
def upload_photo():
    file = request.files.get("photo")
    legende = request.form.get("legende", "").strip()

    if not file or file.filename == "":
        flash("Aucun fichier sélectionné.", "error")
        return redirect(url_for("galerie"))

    if not allowed_file(file.filename):
        flash("Format non supporté (png, jpg, jpeg, gif, webp).", "error")
        return redirect(url_for("galerie"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"{datetime.utcnow().timestamp()}_{current_user.id}.{ext}")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    photo = Photo(uploader_id=current_user.id, filename=filename, legende=legende)
    db.session.add(photo)
    db.session.commit()

    socketio.emit("nouvelle_photo", photo.to_dict(), room=ROOM)
    return redirect(url_for("galerie"))


@app.route("/projets")
@login_required
def projets():
    liste = Projet.query.order_by(Projet.created_at.desc()).all()
    return render_template("projets.html", projets=liste)


@app.route("/projets/creer", methods=["POST"])
@login_required
def creer_projet():
    titre = request.form.get("titre", "").strip()
    description = request.form.get("description", "").strip()
    if not titre:
        flash("Le titre est obligatoire.", "error")
        return redirect(url_for("projets"))

    projet = Projet(titre=titre, description=description, created_by=current_user.id)
    db.session.add(projet)
    db.session.commit()
    socketio.emit("nouveau_projet", projet.to_dict(), room=ROOM)
    return redirect(url_for("projets"))


@app.route("/projets/<int:projet_id>/statut", methods=["POST"])
@login_required
def changer_statut_projet(projet_id):
    projet = db.session.get(Projet, projet_id)
    if not projet:
        return jsonify({"error": "Projet introuvable"}), 404

    nouveau_statut = request.json.get("statut")
    if nouveau_statut not in ("a_faire", "en_cours", "termine"):
        return jsonify({"error": "Statut invalide"}), 400

    projet.statut = nouveau_statut
    db.session.commit()
    socketio.emit("projet_maj", projet.to_dict(), room=ROOM)
    return jsonify(projet.to_dict())


@app.route("/carte")
@login_required
def carte():
    autre = User.query.filter(User.id != current_user.id).first()
    distance = None
    if (
        current_user.latitude
        and current_user.longitude
        and autre
        and autre.latitude
        and autre.longitude
    ):
        distance = round(
            haversine(
                current_user.latitude,
                current_user.longitude,
                autre.latitude,
                autre.longitude,
            ),
            1,
        )
    return render_template("carte.html", autre=autre, distance=distance)


@app.route("/api/position", methods=["POST"])
@login_required
def update_position():
    data = request.get_json()
    lat = data.get("latitude")
    lon = data.get("longitude")
    ville = data.get("ville")

    if lat is None or lon is None:
        return jsonify({"error": "Coordonnées manquantes"}), 400

    current_user.latitude = lat
    current_user.longitude = lon
    current_user.last_location_update = datetime.utcnow()
    if ville:
        current_user.ville = ville
    db.session.commit()

    autre = User.query.filter(User.id != current_user.id).first()
    distance = None
    if autre and autre.latitude and autre.longitude:
        distance = round(haversine(lat, lon, autre.latitude, autre.longitude), 1)

    payload = {
        "user_id": current_user.id,
        "latitude": lat,
        "longitude": lon,
        "ville": current_user.ville,
        "distance_km": distance,
    }
    socketio.emit("position_maj", payload, room=ROOM)
    return jsonify(payload)


# ---------------------------------------------------------------------------
# SocketIO — chat temps réel
# ---------------------------------------------------------------------------


@socketio.on("connect")
def on_connect():
    if current_user.is_authenticated:
        join_room(ROOM)
        emit(
            "utilisateur_connecte",
            {"user_id": current_user.id, "nom": current_user.nom},
            room=ROOM,
        )


@socketio.on("envoyer_message")
def on_envoyer_message(data):
    if not current_user.is_authenticated:
        return
    content = (data.get("content") or "").strip()
    if not content:
        return

    message = Message(sender_id=current_user.id, content=content)
    db.session.add(message)
    db.session.commit()

    emit("nouveau_message", message.to_dict(), room=ROOM)


@socketio.on("en_train_decrire")
def on_typing(data):
    if current_user.is_authenticated:
        emit(
            "en_train_decrire_broadcast",
            {"user_id": current_user.id, "nom": current_user.nom},
            room=ROOM,
            include_self=False,
        )


# ---------------------------------------------------------------------------
# Manifest PWA / service worker (servis depuis /static, routes de secours)
# ---------------------------------------------------------------------------


def creer_compte_si_absent(username, nom, password, couleur):
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(
            username=username,
            nom=nom,
            password_hash=generate_password_hash(password),
            couleur=couleur,
        )
        db.session.add(user)
        db.session.commit()
        print(f"Compte créé : {username} / mot de passe : {password}")


def init_db():
    with app.app_context():
        os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
        db.create_all()
        # Comptes par défaut à modifier après premier lancement !
        creer_compte_si_absent("nico", "Nico", "changeMoi123", "#6C63FF")
        creer_compte_si_absent("copine", "Copine", "changeMoi123", "#FF6B9D")


if __name__ == "__main__":
    init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    socketio.run(app, host="0.0.0.0", port=5001, debug=debug_mode)
