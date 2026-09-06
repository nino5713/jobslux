# Espace privé (nom de code du projet : "nous-deux")

Application web privée (PWA) pour vous deux : chat en temps réel, galerie photo partagée, projets communs et distance en temps réel entre vos deux positions. **Camouflée** derrière une fausse page d'erreur.

## Fonctionnalités

- **Chat temps réel** (Flask-SocketIO) avec indicateur "en train d'écrire"
- **Galerie photo** partagée, mise à jour en direct
- **Projets communs** façon kanban (à faire / en cours / terminé)
- **Distance en temps réel** entre vous deux (géolocalisation navigateur + formule de Haversine)
- **PWA installable** sur téléphone, sous un nom neutre ("Outils Système") avec une icône générique
- **Camouflage** : la page d'accueil affiche une fausse erreur 503. Il faut taper le mot de code dans le champ vide en dessous pour accéder à la vraie connexion. Une fois déverrouillé, ça reste mémorisé pendant 1 an (cookie de session) — pas besoin de retaper le mot à chaque fois sur le même appareil.

## Comment fonctionne le camouflage

- `/` affiche toujours la fausse page d'erreur (HTTP 503) tant que la session n'est pas déverrouillée
- Taper le mot de code (par défaut `étoile`, insensible aux accents/majuscules) dans le champ et appuyer sur Entrée déverrouille et redirige vers `/login`
- **Toutes** les autres routes (`/chat`, `/login`, `/galerie`, etc.) redirigent automatiquement vers la fausse page si la session n'est pas déverrouillée — impossible de deviner une URL et de tomber directement sur l'app
- Le mot de code se change via la variable d'environnement `MOT_DE_CODE` (voir le fichier service systemd plus bas)

## Installation locale (test)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

L'app tourne sur `http://localhost:5001`.

Deux comptes sont créés automatiquement au premier lancement :

| Identifiant | Mot de passe   |
|-------------|----------------|
| `nico`      | `changeMoi123` |
| `copine`    | `changeMoi123` |

**⚠️ Change ces mots de passe immédiatement** (voir section ci-dessous).

## Changer les identifiants / mots de passe

Le plus simple, en ligne de commande Python dans le dossier du projet :

```python
from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    user = User.query.filter_by(username="nico").first()
    user.password_hash = generate_password_hash("NOUVEAU_MOT_DE_PASSE")
    user.username = "nouveau_identifiant"  # si tu veux aussi changer l'identifiant
    db.session.commit()
```

Tu peux aussi changer le `nom` et la `couleur` (code hex) de chacun de la même manière.

## Déploiement sur ton VPS (pattern habituel)

1. Pousse le code sur GitHub (nouveau repo, ex: `nous-deux`)
2. Sur le VPS :
   ```bash
   git clone https://github.com/<toi>/nous-deux.git
   cd nous-deux
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 -c "from app import init_db; init_db()"
   ```
3. Change immédiatement les mots de passe par défaut (voir ci-dessus)
4. Crée un service systemd, par exemple `/etc/systemd/system/nous-deux.service` :
   ```ini
   [Unit]
   Description=Nous Deux
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/chemin/vers/nous-deux
   Environment="SECRET_KEY=une-longue-cle-aleatoire"
   Environment="MOT_DE_CODE=etoile"
   ExecStart=/chemin/vers/nous-deux/venv/bin/python app.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
5. `systemctl daemon-reload && systemctl enable --now nous-deux`
6. Mets un reverse proxy Nginx devant (port 5001 → 443 en HTTPS), **important** : la géolocalisation navigateur ne fonctionne que sur HTTPS (ou localhost) !
7. Pense à activer le WebSocket dans la config Nginx (`proxy_set_header Upgrade $http_upgrade;` etc.) pour que le chat temps réel fonctionne.

### ⚠️ Point d'attention HTTPS
`navigator.geolocation` est bloqué par les navigateurs sur les sites en simple HTTP. Un certificat Let's Encrypt (via Certbot) est indispensable pour que la page "Distance" fonctionne une fois déployée.

## ⚠️ Limites du camouflage à connaître

- Si quelqu'un consulte l'historique du navigateur ou les mots de passe enregistrés, l'URL du site (ex: `nous-deux-socom.lu`) peut rester visible — choisis un nom de domaine qui ne trahit rien lui non plus
- Sur Android/iOS, l'aperçu de l'app dans le multitâche (liste des apps récentes) montre une capture d'écran de ce qui était affiché — pense à quitter/verrouiller le téléphone plutôt que de laisser l'app ouverte en arrière-plan sur une page sensible
- Le nom "Outils Système" et l'icône grise sont volontairement neutres ; libre à toi de me demander un autre nom de camouflage si tu préfères

## Idées d'évolutions futures

- Notifications push (via service worker) quand un message arrive
- Carte visuelle avec les deux positions (Leaflet.js + OpenStreetMap, gratuit)
- Historique de la distance dans le temps (graphique)
- Compteur de jours avant la prochaine visite prévue
- Messages vocaux courts
- Mode sombre
