import logging
import json
from odoo import http, fields
from odoo.http import request

class PosLivraisonController(http.Controller):
    # ==== Helpers: session & payloads ====
    def _extract_motif_from_notes(self, notes):
        """Best-effort extraction of motif from notes string for stock-out entries.
        Expected pattern example: "... | Sortie de stock: <MOTIF> - <qty> sacs - <montant> FC"
        """
        try:
            if not notes:
                return None
            key = 'Sortie de stock:'
            idx = notes.find(key)
            if idx == -1:
                return None
            rest = notes[idx + len(key):].lstrip()
            # motif ends before the next ' - '
            motif = rest.split(' - ')[0].strip()
            return motif or None
        except Exception:
            return None
    def _get_open_session_id_for_user(self, uid=None):
        uid = uid or request.env.user.id
        return request.env['pos.livraison.session']._get_open_for_user(uid)

    def _ensure_open_session_for_user(self, uid=None):
        uid = uid or request.env.user.id
        return request.env['pos.livraison.session']._ensure_open_for_user(uid)

    def _session_to_payload(self, s):
        if not s:
            return None
        return {
            'id': s.id,
            'name': s.name,
            'date': s.date and s.date.isoformat() or None,
            'date_cloture': s.date_cloture and s.date_cloture.isoformat() or None,
            'user_id': s.user_id.id,
            'user_name': s.user_id.name,
            'state': s.state,
            'stats': {
                'total_livraisons': s.total_livraisons,
                'montant_livre_total': s.montant_livre_total,
                'sacs_livres_total': s.sacs_livres_total,
                'sorties_sacs_total': s.sorties_sacs_total,
                'sorties_kg_total': s.sorties_kg_total,
            }
        }

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

    # ==== Livraison sessions API ====
    @http.route('/api/livraison/session/status', type='json', auth='user', methods=['GET', 'POST'])
    def session_status(self):
        sid = self._get_open_session_id_for_user()
        session = sid and request.env['pos.livraison.session'].browse(sid) or False
        return {
            'status': 'success',
            'data': {
                'has_open': bool(sid),
                'session': self._session_to_payload(session) if session else None,
            }
        }

    # Explicit JSON-only variant to avoid method/content-type confusion
    @http.route('/api/livraison/session/status/json', type='json', auth='user', methods=['POST'])
    def session_status_json(self):
        return self.session_status()

    # HTTP variant for manual checks in browser
    @http.route('/api/livraison/session/status/http', type='http', auth='user', methods=['GET'], csrf=False)
    def session_status_http(self):
        payload = self.session_status()
        return request.make_response(json.dumps(payload), headers=[('Content-Type', 'application/json')])

    @http.route('/api/livraison/session/open', type='json', auth='user', methods=['POST'])
    def session_open(self):
        sid = self._get_open_session_id_for_user()
        if not sid:
            sid = self._ensure_open_session_for_user()
        session = request.env['pos.livraison.session'].browse(sid)
        return {'status': 'success', 'data': self._session_to_payload(session)}

    @http.route('/api/livraison/session/close', type='json', auth='user', methods=['POST'])
    def session_close(self):
        sid = self._get_open_session_id_for_user()
        if not sid:
            return {'status': 'error', 'code': 'no_open_session', 'message': "Aucune session ouverte"}
        session = request.env['pos.livraison.session'].browse(sid)
        if session.user_id.id != request.env.user.id and not request.env.user.has_group('base.group_system'):
            return {'status': 'error', 'code': 'forbidden', 'message': "Vous ne pouvez pas fermer la session d'un autre utilisateur"}
        session.action_close_session()
        return {'status': 'success', 'data': self._session_to_payload(session)}

    @http.route('/api/livraison/commandes', type='json', auth='user', methods=['POST'])
    def get_commandes(self, **params):
        logging.info("=========== les paramettres dans /api/livraison/commandes: %s", params)
        # Filtre de base : seulement les commandes avec un état de livraison défini
        domain = [('etat_livraison', '!=', False)]
        etat = params.get('etat') or params.get('etat_livraison')
        if etat:
            domain.append(('etat_livraison', '=', etat))
        else:
            # Par défaut, exclure les commandes livrées et annulées
            domain.append(('etat_livraison', 'not in', ['livree', 'annulee']))
        priority = params.get('priority') or params.get('priority_livraison')
        if priority:
            domain.append(('priority_livraison', '=', priority))
        search = params.get('search')
        if search:
            domain += ['|', ('name', 'ilike', search), ('client_name', 'ilike', search)]
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 80)) if params.get('limit') else None
        commandes = request.env['pos.caisse.commande'].search(domain, offset=offset, limit=limit, order='priority_livraison desc, create_date asc')
        data = [{
            'id': c.id,
            'name': c.name,
            'client_card': getattr(c, 'client_card', False),
            'client_nom': c.client_name or '',
            'is_vc': getattr(c, 'is_vc', False),
            'montant_total': c.montant_total,
            'montant_cible': getattr(c, 'montant_cible', c.montant_total),
            'montant_livre': getattr(c, 'montant_livre', 0.0),
            'montant_restant': getattr(c, 'montant_restant', c.montant_total),
            'etat_livraison': getattr(c, 'etat_livraison', 'en_queue') or 'en_queue',
            'priority_livraison': getattr(c, 'priority_livraison', '0') or '0',
            'progression': getattr(c, 'progression', 0.0),
            'date_livraison_prevue': getattr(c, 'date_livraison_prevue', None) and c.date_livraison_prevue.isoformat() or None,
        } for c in commandes]
        total_count = request.env['pos.caisse.commande'].search_count(domain)
        return {'status': 'success', 'data': data, 'total': total_count, 'offset': offset, 'returned': len(data)}

    @http.route('/api/livraison/livraisons', type='json', auth='user', methods=['POST'])
    def list_livraisons(self, **params):
        """List delivery records constrained by session by default.
        Params:
          - session_mode: 'current' (default) | 'session_id' | 'none'
          - session_id: required if session_mode == 'session_id'
          - commande_id: filter by a given order
          - date_from/date_to (ISO8601) optional
          - search: ilike on name or livreur
          - offset, limit, order
        """
        logging.info("=========== les paramettres dans /api/livraison/livraisons: %s", params)
        env = request.env
        domain = []
        session_mode = params.get('session_mode', 'current')
        if session_mode == 'current':
            sid = self._get_open_session_id_for_user()
            if not sid:
                # For reports, allow access to all sessions instead of failing
                logging.info("No open session, switching to 'none' mode for report access")
                session_mode = 'none'
            else:
                domain.append(('session_id', '=', sid))
        elif session_mode == 'session_id':
            sid = int(params.get('session_id') or 0)
            if not sid:
                return {'status': 'error', 'message': 'session_id requis'}
            sess = env['pos.livraison.session'].browse(sid)
            if not sess.exists():
                return {'status': 'error', 'message': 'Session inconnue'}
            # Restrict to own session unless admin
            if sess.user_id.id != env.user.id and not env.user.has_group('base.group_system'):
                return {'status': 'error', 'code': 'forbidden', 'message': "Accès refusé à la session demandée"}
            domain.append(('session_id', '=', sid))
        # else 'none' => no session filter (use cautiously)

        if params.get('commande_id'):
            domain.append(('commande_id', '=', int(params['commande_id'])))

        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        search = params.get('search')
        if search:
            domain += ['|', ('name', 'ilike', search), ('livreur', 'ilike', search)]

        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 80)) if params.get('limit') else None
        order = params.get('order', 'date desc')
        Liv = env['pos.livraison.livraison']
        livs = Liv.search(domain, offset=offset, limit=limit, order=order)
        total = Liv.search_count(domain)
        data = [{
            'id': l.id,
            'name': l.name,
            'date': l.date and l.date.isoformat() or None,
            'commande_id': l.commande_id.id if l.commande_id else None,
            'commande_name': l.commande_id.name if l.commande_id else (getattr(l, 'is_sortie_stock', False) and 'Sortie de stock' or None),
            'montant_livre': l.montant_livre,
            'sacs_farine': l.sacs_farine,
            'prix_sac': l.prix_sac,
            'type_paiement': l.type_paiement,
            'motif': (self._extract_motif_from_notes(l.notes) if getattr(l, 'is_sortie_stock', False) else None),
            'livreur': l.livreur or (l.livreur_id and l.livreur_id.name) or None,
            'livreur_id': l.livreur_id.id if l.livreur_id else None,
            'notes': l.notes,
            'session_id': l.session_id.id,
            'livraison_session_id': l.session_id.id,
            'is_sortie_stock': getattr(l, 'is_sortie_stock', False),
        } for l in livs]
        return {'status': 'success', 'data': data, 'total': total, 'offset': offset, 'returned': len(data)}

    @http.route('/api/livraison/commande/<int:commande_id>', type='json', auth='user', methods=['GET'])
    def get_commande_detail(self, commande_id):
        c = request.env['pos.caisse.commande'].browse(commande_id)
        if not c.exists():
            return {'status': 'error', 'message': 'Commande non trouvée'}
        # Limit delivered lines to current session if one is open, to avoid showing other users' deliveries.
        sid = self._get_open_session_id_for_user()
        livs = c.livraison_ids
        if sid:
            livs = livs.filtered(lambda l: l.session_id.id == sid)
        livraisons = [{
            'id': l.id,
            'name': l.name,
            'date': l.date and l.date.isoformat() or None,
            'montant_livre': l.montant_livre,
            'sacs_farine': l.sacs_farine,
            'prix_sac': l.prix_sac,
            'type_paiement': l.type_paiement,
            'motif': (self._extract_motif_from_notes(l.notes) if getattr(l, 'is_sortie_stock', False) else None),
            'livreur': l.livreur or (l.livreur_id and l.livreur_id.name) or None,
            'livreur_id': l.livreur_id.id if l.livreur_id else None,
            'notes': l.notes,
            'session_id': l.session_id.id,
            'livraison_session_id': l.session_id.id,
            'is_sortie_stock': getattr(l, 'is_sortie_stock', False),
        } for l in livs]
        return {'status': 'success', 'data': {
            'id': c.id,
            'name': c.name,
            'client_card': getattr(c, 'client_card', False),
            'client_nom': c.client_name or '',
            'is_vc': getattr(c, 'is_vc', False),
            'montant_total': c.montant_total,
            'montant_cible': getattr(c, 'montant_cible', c.montant_total),
            'montant_livre': getattr(c, 'montant_livre', 0.0),
            'montant_restant': getattr(c, 'montant_restant', c.montant_total),
            'etat_livraison': getattr(c, 'etat_livraison', 'en_queue') or 'en_queue',
            'priority_livraison': getattr(c, 'priority_livraison', '0') or '0',
            'notes_livraison': getattr(c, 'notes_livraison', ''),
            'mode_livraison': getattr(c, 'mode_livraison', 'standard'),
            'date_livraison_prevue': getattr(c, 'date_livraison_prevue', None) and c.date_livraison_prevue.isoformat() or None,
            'date_livraison_complete': getattr(c, 'date_livraison_complete', None) and c.date_livraison_complete.isoformat() or None,
            'sacs_farine_total': getattr(c, 'sacs_farine_total', 0),
            'poids_farine_kg': getattr(c, 'poids_farine_kg', 0.0),
            'progression': getattr(c, 'progression', 0.0),
            'montant_livre_cash': getattr(c, 'montant_livre_cash', 0.0),
            'montant_livre_bp': getattr(c, 'montant_livre_bp', 0.0),
            'livraisons': livraisons,
        }}

    @http.route('/api/livraison/nouvelle_livraison', type='json', auth='user', methods=['POST'])
    def create_livraison(self, **payload):
        logging.getLogger(__name__).info("================ Creating new livraison with payload: %s", payload)
        
        params = http.request.jsonrequest or payload
        logging.info("=================== Payload received: %s", params)
        try:
            # Enforce an open session for API usage to reflect client UX
            sid = self._get_open_session_id_for_user()
            if not sid:
                return {'status': 'error', 'code': 'no_open_session', 'message': "Ouvrez d'abord une session de livraison"}
            commande_id = params.get('commande_id') or params.get('commande')
            montant_livre = params.get('montant_livre')
            type_paiement = params.get('type_paiement', 'cash')
            livreur = params.get('livreur')
            livreur_id = params.get('livreur_id')
            client_sid = params.get('livraison_session_id')
            notes = params.get('notes')
            # If client provided a livraison_session_id, ensure it matches the current open session for safety
            if client_sid and int(client_sid) != int(sid):
                return {'status': 'error', 'code': 'session_mismatch', 'message': "Session liv. fournie ne correspond pas à la session ouverte"}
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
            # Respecte le montant cible (VC => +25%)
            cible = getattr(c, 'montant_cible', c.montant_total)
            montant_livre_actuel = getattr(c, 'montant_livre', 0.0)
            if montant_livre_actuel + montant_livre > (cible or 0.0) + 0.01:
                return {'status': 'error', 'message': 'Montant dépasse le total cible'}
            vals = {
                'commande_id': c.id,
                'montant_livre': montant_livre,
                'type_paiement': type_paiement,
                'livreur': livreur,
                'notes': notes,
                'session_id': sid,
            }
            if livreur_id:
                try:
                    vals['livreur_id'] = int(livreur_id)
                except Exception:
                    pass
            livraison = request.env['pos.livraison.livraison'].create(vals)
            montant_restant_actuel = getattr(c, 'montant_restant', c.montant_total)
            etat_actuel = getattr(c, 'etat_livraison', 'en_queue')
            if montant_restant_actuel <= 0 and etat_actuel != 'livree':
                c.action_complete_livraison()
            elif etat_actuel == 'en_queue':
                c.action_start_livraison()
            return {'status': 'success', 'livraison_id': livraison.id}
        except Exception as e:
            request.env.cr.rollback()
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/livraison/queue', type='json', auth='user', methods=['GET'])
    def get_queue(self):
        commandes = request.env['pos.caisse.commande'].search([
            ('etat_livraison', '!=', False),
            ('etat_livraison', '=', 'en_queue')
        ], order='priority_livraison desc, create_date asc')
        data = [{
            'position': i + 1,
            'id': c.id,
            'name': c.name,
            'client_nom': c.client_name or '',
            'montant_total': c.montant_total,
            'priority_livraison': getattr(c, 'priority_livraison', '0') or '0',
            'progression': getattr(c, 'progression', 0.0),
        } for i, c in enumerate(commandes)]
        return {'status': 'success', 'data': data}

    @http.route('/api/livraison/stats', type='json', auth='user', methods=['GET'])
    def get_stats(self):
        env = request.env
        model = env['pos.caisse.commande']
        states = ['en_queue', 'en_cours', 'livree_partielle', 'livree']
        counts = {s: model.search_count([('etat_livraison', '=', s)]) for s in states}
        today = fields.Date.today()
        # Session-aware: only show current user's open session activity if present
        sid = self._get_open_session_id_for_user()
        liv_domain = [('date', '>=', today)]
        sortie_domain = [('date', '>=', today)]
        if sid:
            liv_domain.append(('session_id', '=', sid))
            sortie_domain.append(('session_id', '=', sid))
        livraisons_today = env['pos.livraison.livraison'].search(liv_domain)
        sorties_today = env['pos.livraison.sortie.stock'].search(sortie_domain)
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
        # Unwrap JSON-RPC envelope if present
        if isinstance(payload, dict) and isinstance(payload.get('params'), dict):
            payload = payload['params']
        logging.info("=========== Creating sortie stock with payload: %s", payload)
        try:
            # Enforce an open session for API usage
            sid = self._get_open_session_id_for_user()
            if not sid:
                return {'status': 'error', 'code': 'no_open_session', 'message': "Ouvrez d'abord une session de livraison"}
            motif = payload.get('motif')
            quantite_sacs = payload.get('quantite_sacs')
            montant = payload.get('montant')
            type_sortie = payload.get('type', 'interne')
            responsable = payload.get('responsable')
            notes = payload.get('notes')
            if not motif:
                return {'status': 'error', 'message': 'motif requis'}
            # Supporte nouveau parametre 'montant' (prioritaire). Convertit en sacs via prix_sac.
            prix_sac = float(request.env['ir.config_parameter'].sudo().get_param('pos_livraison.prix_sac', '222000'))
            if montant not in (None, '', False):
                try:
                    montant = float(montant)
                except Exception:
                    return {'status': 'error', 'message': 'montant invalide'}
                if montant <= 0:
                    return {'status': 'error', 'message': 'montant doit être > 0'}
                quant_calc = (montant / prix_sac) if prix_sac > 0 else 0.0
                quantite_sacs = quant_calc
            else:
                try:
                    quantite_sacs = float(quantite_sacs)
                except Exception:
                    return {'status': 'error', 'message': 'quantite_sacs invalide'}
                if quantite_sacs <= 0:
                    return {'status': 'error', 'message': 'quantite_sacs doit être > 0'}
                # Si pas de montant fourni, déduire pour la livraison
                montant = quantite_sacs * prix_sac
            env = request.env
            sortie = env['pos.livraison.sortie.stock'].create({
                'motif': motif,
                'quantite_sacs': quantite_sacs,
                'type': type_sortie,
                'responsable': responsable,
                'notes': notes,
                'session_id': sid,
            })
            # Créer une livraison liée à la session, marquée comme "sortie de stock" pour les rapports
            try:
                sess = env['pos.livraison.session'].browse(sid)
                livreur_name = sess.user_id.name if sess and sess.exists() else env.user.name
                liv = env['pos.livraison.livraison'].create({
                    'commande_id': False,
                    'session_id': sid,
                    'montant_livre': float(montant or 0.0),
                    'type_paiement': 'cash',
                    'livreur': livreur_name,
                    'livreur_id': sess.user_id.id if sess and sess.exists() else env.user.id,
                    'notes': (notes and (notes + ' | ') or '') + f"Sortie de stock: {motif} - {quantite_sacs:.2f} sacs - {montant:.0f} FC",
                    'is_sortie_stock': True,
                })
                # Optional: attach a synthetic commande_name in API layer when commande is False
            except Exception:
                liv = None
            return {'status': 'success', 'sortie_id': sortie.id, 'livraison_id': liv and liv.id}
        except Exception as e:
            request.env.cr.rollback()
            return {'status': 'error', 'message': str(e)}
