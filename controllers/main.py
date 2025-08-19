import logging
import json
from odoo import http, fields
from odoo.http import request

class PosLivraisonController(http.Controller):
    def _compute_user_role_payload(self):
        user = request.env.user
        g = lambda xmlid: user.has_group(xmlid)
        is_admin = g('base.group_system') or user.id == 1
        caisse_user = g('pos_caisse.group_pos_caisse_user')
        caisse_manager = g('pos_caisse.group_pos_caisse_manager')
        livraison_user = g('pos_livraison.group_pos_livraison_user')
        livraison_manager = g('pos_livraison.group_pos_livraison_manager')
        paie_user = g('pos_paie.group_pos_paie_user')
        paie_manager = g('pos_paie.group_pos_paie_manager')
        admin_user = g('pos_admin.group_pos_admin_user')
        admin_manager = g('pos_admin.group_pos_admin_manager')
        # Screens reflect actual group rights; only superuser gets all screens
        if is_admin:
            screens = {k: True for k in ['caisse', 'livraison', 'paie', 'administration']}
        else:
            screens = {
                'caisse': bool(caisse_user or caisse_manager),
                'livraison': bool(livraison_user or livraison_manager),
                'paie': bool(paie_user or paie_manager),
                'administration': bool(admin_user or admin_manager),
            }
        return {
            'status': 'success',
            'data': {
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'login': user.login,
                    'is_admin': bool(is_admin),
                },
                'screens': screens,
                'groups': {
                    'pos_caisse_user': caisse_user,
                    'pos_caisse_manager': caisse_manager,
                    'pos_livraison_user': livraison_user,
                    'pos_livraison_manager': livraison_manager,
                    'pos_paie_user': paie_user,
                    'pos_paie_manager': paie_manager,
                    'pos_admin_user': admin_user,
                    'pos_admin_manager': admin_manager,
                }
            }
        }

    @http.route('/api/user/role/json', type='json', auth='user', methods=['POST'])
    def get_user_role_json(self):
        """JSON variant on a separate URL to avoid route conflicts."""
        return self._compute_user_role_payload()

    # Primary endpoint used by mobile: POSTing JSON marks the request as type 'json' in Odoo.
    # Declare this route as type='json' to avoid mismatch errors.
    @http.route('/api/user/role', type='json', auth='user', methods=['POST'])
    def get_user_role(self, **_params):
        """Primary endpoint for clients (POST with application/json)."""
        return self._compute_user_role_payload()

    # Optional: simple GET for quick manual checks from a browser
    @http.route('/api/user/role/http', type='http', auth='user', methods=['GET'], csrf=False)
    def get_user_role_http(self):
        payload = self._compute_user_role_payload()
        return request.make_response(
            json.dumps(payload),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/api/livraison/commandes', type='json', auth='user', methods=['POST'])
    def get_commandes(self, **params):
        domain = []
        etat = params.get('etat') or params.get('etat_livraison')
        if etat:
            domain.append(('etat_livraison', '=', etat))
        priority = params.get('priority') or params.get('priority_livraison')
        if priority:
            domain.append(('priority_livraison', '=', priority))
        search = params.get('search')
        if search:
            domain += ['|', ('name', 'ilike', search), ('client_nom', 'ilike', search)]
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 80)) if params.get('limit') else None
        commandes = request.env['pos.caisse.commande'].search(domain, offset=offset, limit=limit, order='priority_livraison desc, create_date asc')
        data = [{
            'id': c.id,
            'name': c.name,
            'client_card': getattr(c, 'client_card', False),
            'client_nom': c.client_nom,
            'montant_total': c.montant_total,
            'montant_livre': c.montant_livre,
            'montant_restant': c.montant_restant,
            'etat_livraison': c.etat_livraison,
            'priority_livraison': c.priority_livraison,
            'progression': c.progression,
            'date_livraison_prevue': c.date_livraison_prevue and c.date_livraison_prevue.isoformat() or None,
        } for c in commandes]
        total_count = request.env['pos.caisse.commande'].search_count(domain)
        return {'status': 'success', 'data': data, 'total': total_count, 'offset': offset, 'returned': len(data)}

    @http.route('/api/livraison/commande/<int:commande_id>', type='json', auth='user', methods=['GET'])
    def get_commande_detail(self, commande_id):
        c = request.env['pos.caisse.commande'].browse(commande_id)
        if not c.exists():
            return {'status': 'error', 'message': 'Commande non trouvée'}
        livraisons = [{
            'id': l.id,
            'name': l.name,
            'date': l.date and l.date.isoformat() or None,
            'montant_livre': l.montant_livre,
            'sacs_farine': l.sacs_farine,
            'prix_sac': l.prix_sac,
            'type_paiement': l.type_paiement,
            'livreur': l.livreur,
            'notes': l.notes,
        } for l in c.livraison_ids]
        return {'status': 'success', 'data': {
            'id': c.id,
            'name': c.name,
            'client_card': getattr(c, 'client_card', False),
            'client_nom': c.client_nom,
            'montant_total': c.montant_total,
            'montant_livre': c.montant_livre,
            'montant_restant': c.montant_restant,
            'etat_livraison': c.etat_livraison,
            'priority_livraison': c.priority_livraison,
            'notes_livraison': c.notes_livraison,
            'mode_livraison': c.mode_livraison,
            'date_livraison_prevue': c.date_livraison_prevue and c.date_livraison_prevue.isoformat() or None,
            'date_livraison_complete': c.date_livraison_complete and c.date_livraison_complete.isoformat() or None,
            'sacs_farine_total': c.sacs_farine_total,
            'poids_farine_kg': c.poids_farine_kg,
            'progression': c.progression,
            'montant_livre_cash': c.montant_livre_cash,
            'montant_livre_bp': c.montant_livre_bp,
            'livraisons': livraisons,
        }}

    @http.route('/api/livraison/nouvelle_livraison', type='json', auth='user', methods=['POST'])
    def create_livraison(self, **payload):
        logging.getLogger(__name__).info("================ Creating new livraison with payload: %s", payload)
        
        params = http.request.jsonrequest or payload
        logging.info("=================== Payload received: %s", params)
        try:
            commande_id = params.get('commande_id') or params.get('commande')
            montant_livre = params.get('montant_livre')
            type_paiement = params.get('type_paiement', 'cash')
            livreur = params.get('livreur')
            notes = params.get('notes')
            if not commande_id:
                return {'status': 'error', 'message': 'commande_id requis'}
            if montant_livre in (None, '', False):
                return {'status': 'error', 'message': 'montant_livre requis'}
            try:
                montant_livre = float(montant_livre)
            except Exception:
                return {'status': 'error', 'message': 'montant_livre invalide'}
            if montant_livre <= 0:
                return {'status': 'error', 'message': 'montant_livre doit être > 0'}
            c = request.env['pos.caisse.commande'].browse(int(commande_id))
            if not c.exists():
                return {'status': 'error', 'message': 'Commande non trouvée'}
            if c.montant_livre + montant_livre > c.montant_total + 0.01:
                return {'status': 'error', 'message': 'Montant dépasse le total'}
            livraison = request.env['pos.livraison.livraison'].create({
                'commande_id': c.id,
                'montant_livre': montant_livre,
                'type_paiement': type_paiement,
                'livreur': livreur,
                'notes': notes,
            })
            if c.montant_restant <= 0 and c.etat_livraison != 'livree':
                c.action_complete_livraison()
            elif c.etat_livraison == 'en_queue':
                c.action_start_livraison()
            return {'status': 'success', 'livraison_id': livraison.id}
        except Exception as e:
            request.env.cr.rollback()
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/livraison/queue', type='json', auth='user', methods=['GET'])
    def get_queue(self):
        commandes = request.env['pos.caisse.commande'].search([
            ('etat_livraison', '=', 'en_queue')
        ], order='priority_livraison desc, create_date asc')
        data = [{
            'position': i + 1,
            'id': c.id,
            'name': c.name,
            'client_nom': c.client_nom,
            'montant_total': c.montant_total,
            'priority_livraison': c.priority_livraison,
            'progression': c.progression,
        } for i, c in enumerate(commandes)]
        return {'status': 'success', 'data': data}

    @http.route('/api/livraison/stats', type='json', auth='user', methods=['GET'])
    def get_stats(self):
        env = request.env
        model = env['pos.caisse.commande']
        states = ['en_queue', 'en_cours', 'livree_partielle', 'livree']
        counts = {s: model.search_count([('etat_livraison', '=', s)]) for s in states}
        today = fields.Date.today()
        livraisons_today = env['pos.livraison.livraison'].search([('date', '>=', today)])
        sorties_today = env['pos.livraison.sortie.stock'].search([('date', '>=', today)])
        return {'status': 'success', 'data': {
            'commandes': {**counts, 'total': sum(counts.values())},
            'livraisons_today': {
                'nombre': len(livraisons_today),
                'sacs_farine': sum(livraisons_today.mapped('sacs_farine')),
                'montant': sum(livraisons_today.mapped('montant_livre')),
            },
            'sorties_today': {
                'nombre': len(sorties_today),
                'sacs_sortis': sum(sorties_today.mapped('quantite_sacs')),
            }
        }}

    @http.route('/api/livraison/sortie_stock', type='json', auth='user', methods=['POST'])
    def create_sortie_stock(self, **params):
        payload = http.request.jsonrequest or params
        logging.info("=========== Creating sortie stock with payload: %s", payload)
        try:
            motif = payload.get('motif')
            quantite_sacs = payload.get('quantite_sacs')
            type_sortie = payload.get('type', 'interne')
            responsable = payload.get('responsable')
            notes = payload.get('notes')
            if not motif:
                return {'status': 'error', 'message': 'motif requis'}
            try:
                quantite_sacs = float(quantite_sacs)
            except Exception:
                return {'status': 'error', 'message': 'quantite_sacs invalide'}
            if quantite_sacs <= 0:
                return {'status': 'error', 'message': 'quantite_sacs doit être > 0'}
            sortie = request.env['pos.livraison.sortie.stock'].create({
                'motif': motif,
                'quantite_sacs': quantite_sacs,
                'type': type_sortie,
                'responsable': responsable,
                'notes': notes,
            })
            return {'status': 'success', 'sortie_id': sortie.id}
        except Exception as e:
            request.env.cr.rollback()
            return {'status': 'error', 'message': str(e)}
