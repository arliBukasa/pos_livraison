{
    'name': 'POS Livraison Sumni v2',
    'version': '15.0.3.0.0',
    'summary': "Gestion livraison intégrée POS: file d'attente, livraisons partielles, stock, API",
    'description': """
Module POS Livraison Sumni v2
- Intégration directe avec pos.caisse.commande
- File d'attente + priorités
- Livraisons partielles (progression %, notifications bus)
- Sorties de stock farine
- Calcul sacs / poids automatique
- API REST mobile (commandes, détails, file, stats, création livraisons / sorties)
""",
    'author': 'Sumni Technologies',
    'website': 'https://sumni.tech',
    'category': 'Point of Sale',
    'depends': ['base', 'web', 'bus', 'pos_caisse'],
    "data": [
        "data/pos_livraison_data.xml",
        "security/ir.model.access.csv",
        "security/pos_livraison_security.xml",
    "views/pos_caisse_commande_views.xml",
    "views/pos_livraison_views.xml",
    "views/pos_livraison_menu.xml"
    ],
    'assets': {
        'web.assets_backend': [],
    },
    'demo': [],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 20,
}
