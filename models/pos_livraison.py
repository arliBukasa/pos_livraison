from odoo import models, fields, api, exceptions

class PosCommande(models.Model):
    _inherit = 'pos.caisse.commande'

    etat_livraison = fields.Selection([
        ('en_queue', "En file d'attente"),
        ('en_cours', 'En cours de livraison'),
        ('livree_partielle', 'Livrée partielle'),
        ('livree', 'Livrée complète'),
        ('annulee', 'Annulée')
    ], default='en_queue', string='État livraison', copy=False, index=True,
       help="Cycle: en_queue -> en_cours -> livree_partielle (si partiel) -> livree. 'annulee' en cas d'annulation.")
    priority_livraison = fields.Selection([
        ('0', 'Normal'), ('1', 'Urgent'), ('2', 'Très urgent')
    ], default='0', string='Priorité livraison', index=True)
    date_livraison_prevue = fields.Datetime('Livraison prévue')
    date_livraison_complete = fields.Datetime('Livraison complétée')
    mode_livraison = fields.Selection([
        ('retrait', 'Retrait sur place'), ('livraison', 'Livraison standard'), ('express', 'Express')
    ], default='livraison', string='Mode de livraison')
    notes_livraison = fields.Text('Notes livraison')
    client_nom = fields.Char('Nom du client', related='client_name', store=True)
    montant_total = fields.Float('Montant total', related='total', store=True)

    livraison_ids = fields.One2many('pos.livraison.livraison', 'commande_id', string='Livraisons')

    sacs_farine_total = fields.Float('Total sacs farine', compute='_compute_sacs_farine', store=True)
    poids_farine_kg = fields.Float('Poids farine (kg)', compute='_compute_poids_farine', store=True)

    montant_livre = fields.Float('Montant livré', compute='_compute_montant_livre', store=True)
    montant_restant = fields.Float('Montant restant', compute='_compute_montant_restant', store=True)
    montant_livre_cash = fields.Float('Montant livré (Cash)', compute='_compute_montants_livres', store=True)
    montant_livre_bp = fields.Float('Montant livré (BP)', compute='_compute_montants_livres', store=True)
    progression = fields.Float('Progression (%)', compute='_compute_progression', store=True)
    last_progress_threshold = fields.Integer('Dernier seuil notifié', default=0, copy=False)
    montant_bp = fields.Float('Montant BP (fin de mois)', default=0.0)

    @api.depends('livraison_ids.montant_livre')
    def _compute_montant_livre(self):
        for rec in self:
            rec.montant_livre = sum(rec.livraison_ids.mapped('montant_livre'))

    @api.depends('montant_total', 'montant_livre')
    def _compute_montant_restant(self):
        for rec in self:
            rec.montant_restant = rec.montant_total - rec.montant_livre

    @api.depends('livraison_ids.sacs_farine')
    def _compute_sacs_farine(self):
        for rec in self:
            rec.sacs_farine_total = sum(rec.livraison_ids.mapped('sacs_farine'))

    @api.depends('sacs_farine_total')
    def _compute_poids_farine(self):
        for rec in self:
            poids_par_sac = float(self.env['ir.config_parameter'].sudo().get_param('pos_livraison.poids_sac', '50'))
            rec.poids_farine_kg = rec.sacs_farine_total * poids_par_sac

    @api.depends('livraison_ids.montant_livre', 'livraison_ids.type_paiement')
    def _compute_montants_livres(self):
        for rec in self:
            rec.montant_livre_cash = sum(rec.livraison_ids.filtered(lambda l: l.type_paiement == 'cash').mapped('montant_livre'))
            rec.montant_livre_bp = sum(rec.livraison_ids.filtered(lambda l: l.type_paiement == 'bp').mapped('montant_livre'))

    @api.depends('montant_livre', 'montant_total')
    def _compute_progression(self):
        for rec in self:
            rec.progression = rec.montant_total and min(100.0, (rec.montant_livre / rec.montant_total) * 100.0) or 0.0

    def _update_state_from_progress(self):
        for rec in self:
            if rec.etat_livraison not in ('annulee',):
                if rec.montant_livre == 0:
                    continue
                if 0 < rec.montant_livre < rec.montant_total - 0.01:
                    rec.etat_livraison = 'livree_partielle'
                elif abs(rec.montant_livre - rec.montant_total) <= 0.01:
                    rec.etat_livraison = 'livree'
                    # Basculer automatiquement la commande en état livré
                    if getattr(rec, 'state', False) and rec.state != 'livre':
                        rec.state = 'livre'
                    if not rec.date_livraison_complete:
                        rec.date_livraison_complete = fields.Datetime.now()

    def _notify_progress_thresholds(self):
        thresholds = [25, 50, 75, 100]
        for rec in self:
            for t in thresholds:
                if rec.progression >= t and rec.last_progress_threshold < t:
                    message = {
                        'commande_id': rec.id,
                        'progression': rec.progression,
                        'seuil': t,
                    }
                    rec._bus_notify('pos_livraison_progress', message, rec.id)
                    rec.last_progress_threshold = t

    def action_start_livraison(self):
        self.filtered(lambda r: r.etat_livraison == 'en_queue').write({'etat_livraison': 'en_cours'})

    def action_complete_livraison(self):
        """Forcer la commande en livrée complète et aligner l'état de base."""
        for rec in self:
            if rec.montant_livre + 0.01 < rec.montant_total:
                raise exceptions.UserError('Impossible: montant livré inférieur au total.')
        # Marquer la livraison complète
        self.write({'etat_livraison': 'livree', 'date_livraison_complete': fields.Datetime.now()})
        # Mettre la commande à l'état livré (sauf si déjà annulée)
        self.filtered(lambda r: getattr(r, 'state', False) and r.state not in ('livre', 'annule'))\
            .write({'state': 'livre'})

    def action_confirmer(self):
        res = super().action_confirmer()
        for rec in self:
            if rec.state == 'en_attente_livraison' and rec.etat_livraison == 'en_queue':
                if rec.type_paiement == 'bp':
                    rec.priority_livraison = '2'
                    rec.montant_bp = rec.montant_total
        return res

    def unlink(self):
        for rec in self:
            if rec.etat_livraison == 'livree':
                raise exceptions.UserError('Suppression interdite pour une commande livrée.')
        return super().unlink()

    def action_open_quick_livraison(self):
        self.ensure_one()
        if self.etat_livraison in ('livree','annulee'):
            raise exceptions.UserError('Commande déjà finalisée.')
        montant = self.montant_restant or 0.0
        if montant <= 0:
            raise exceptions.UserError('Rien à livrer.')
        ctx = {
            'default_commande_id': self.id,
            'default_montant_livre': montant,
            'default_type_paiement': getattr(self, 'type_paiement', 'cash'),
        }
        return {
            'name': 'Nouvelle livraison',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.livraison.livraison',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def write(self, vals):
        # Track old states for notification
        old_states = {rec.id: rec.etat_livraison for rec in self}
        res = super().write(vals)
        if 'etat_livraison' in vals:
            for rec in self:
                old_state = old_states.get(rec.id)
                if rec.etat_livraison != old_state:
                    # Si la livraison devient complète, basculer la commande en 'livre'
                    if rec.etat_livraison == 'livree' and getattr(rec, 'state', False) and rec.state != 'livre':
                        # Éviter de modifier si la commande est annulée
                        if rec.state != 'annule':
                            rec.write({'state': 'livre', 'date_livraison_complete': rec.date_livraison_complete or fields.Datetime.now()})
                    message = {
                        'commande_id': rec.id,
                        'old_state': old_state,
                        'new_state': rec.etat_livraison,
                    }
                    rec._bus_notify('pos_livraison_state', message, rec.id)
        return res

    def _bus_notify(self, channel, payload, rec_id=None):
        """Robust bus notifier that adapts to different Odoo bus APIs.
        - Tries _sendmany with triples (target, notification_type, message).
        - Falls back to _sendone(target, notification_type, message) or _sendone(target, message).
        - Finally tries sendone(target, message).
        Never raises to avoid breaking core flows.
        """
        try:
            bus = self.env['bus.bus']
            target = (channel, rec_id) if rec_id is not None else channel
            # Try _sendmany with triple signature
            if hasattr(bus, '_sendmany'):
                try:
                    bus._sendmany([(target, 'simple', payload)])
                    return
                except Exception:
                    pass
            # Try _sendone triple then double
            if hasattr(bus, '_sendone'):
                try:
                    bus._sendone(target, 'simple', payload)
                    return
                except TypeError:
                    try:
                        bus._sendone(target, payload)
                        return
                    except Exception:
                        pass
            # Fallback public sendone if present
            if hasattr(bus, 'sendone'):
                try:
                    bus.sendone(target, payload)
                    return
                except Exception:
                    pass
        except Exception:
            # Silently ignore bus failures
            return

    def action_quick_full_deliver(self):
        """Create a livraison record with the remaining amount and close if fully delivered.
        Returns a client action to reload the form."""
        self.ensure_one()
        if self.etat_livraison in ('livree', 'annulee'):
            raise exceptions.UserError('Commande déjà finalisée.')
        montant = round(self.montant_restant or 0.0, 2)
        if montant <= 0:
            raise exceptions.UserError('Rien à livrer.')
        # Create the partial (or final) delivery silently
        self.env['pos.livraison.livraison'].create({
            'commande_id': self.id,
            'montant_livre': montant,
            'type_paiement': getattr(self, 'type_paiement', 'cash'),
        })
        # After creation, if now fully delivered ensure state complete
        if abs(self.montant_restant) <= 0.01 and self.etat_livraison != 'livree':
            self.action_complete_livraison()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

class LivraisonLivraison(models.Model):
    _name = 'pos.livraison.livraison'
    _description = 'Livraison partielle'
    _order = 'date desc'

    name = fields.Char('Référence', required=True, copy=False, readonly=True, default='Nouveau')
    commande_id = fields.Many2one('pos.caisse.commande', string='Commande', required=False, ondelete='cascade', index=True)
    session_id = fields.Many2one('pos.livraison.session', string='Session livraison', required=False, index=True)
    date = fields.Datetime('Date livraison', default=fields.Datetime.now, required=True, index=True)
    montant_livre = fields.Float('Montant livré', required=True)
    prix_sac = fields.Float('Prix par sac', compute='_compute_prix_sac', store=True)
    type_paiement = fields.Selection([('cash', 'Cash'), ('bp', 'BP')], default='cash', string='Type paiement', index=True)
    livreur = fields.Char('Livreur')
    notes = fields.Text('Notes de livraison')
    sacs_farine = fields.Float('Sacs de farine', compute='_compute_sacs_farine', store=True)
    # Marqueur: livraison créée suite à une sortie de stock (sans commande)
    is_sortie_stock = fields.Boolean('Issue de sortie de stock', default=False, index=True, help="Créée automatiquement depuis une sortie de stock")
    # Aliases explicitly requested by mobile client
    livraison_session_id = fields.Many2one('pos.livraison.session', string='Session livraison (alias)', related='session_id', store=True, index=True)
    livreur_id = fields.Many2one('res.users', string='Livreur (utilisateur)', index=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nouveau') == 'Nouveau':
            vals['name'] = self.env['ir.sequence'].next_by_code('pos.livraison.livraison') or 'Nouveau'
        # Ensure session if not provided
        if not vals.get('session_id'):
            # Accept alias from client or ensure current open
            sid = vals.get('livraison_session_id') or self.env['pos.livraison.session']._ensure_open_for_user(self.env.uid)
            vals['session_id'] = sid
        # Default livreur_id from session or current user if not provided
        if not vals.get('livreur_id'):
            try:
                sess = self.env['pos.livraison.session'].browse(vals.get('session_id'))
                vals['livreur_id'] = (sess.user_id.id if sess and sess.exists() else self.env.uid)
            except Exception:
                vals['livreur_id'] = self.env.uid
        commande = None
        if vals.get('commande_id'):
            commande = self.env['pos.caisse.commande'].browse(vals['commande_id'])
            if commande and commande.exists():
                if commande.montant_livre + vals.get('montant_livre', 0) > commande.montant_total + 0.01:
                    raise exceptions.UserError('Le montant cumulé des livraisons dépasse le total de la commande.')
        rec = super().create(vals)
        # Add bus notification after creation
        if rec.commande_id:
            message = {
                'commande_id': rec.commande_id.id,
                'livraison_id': rec.id,
                'montant_livre': rec.montant_livre,
                'progression': rec.commande_id.progression,
                'etat_livraison': rec.commande_id.etat_livraison,
            }
            rec.commande_id._bus_notify('pos_livraison_new_livraison', message, rec.commande_id.id)
        if commande:
            commande._update_state_from_progress()
            commande._notify_progress_thresholds()
        return rec

    @api.depends('montant_livre')
    def _compute_prix_sac(self):
        for rec in self:
            rec.prix_sac = float(self.env['ir.config_parameter'].sudo().get_param('pos_livraison.prix_sac', '222000'))

    @api.depends('montant_livre', 'prix_sac')
    def _compute_sacs_farine(self):
        for rec in self:
            rec.sacs_farine = rec.prix_sac > 0 and rec.montant_livre / rec.prix_sac or 0

    def write(self, vals):
        # Validate session state if changed
        if 'session_id' in vals and vals['session_id']:
            sess = self.env['pos.livraison.session'].browse(vals['session_id'])
            if sess and sess.state == 'ferme':
                raise exceptions.UserError("Impossible d'attacher une livraison à une session fermée.")
        res = super().write(vals)
        for rec in self:
            if rec.commande_id:
                rec.commande_id._update_state_from_progress()
                rec.commande_id._notify_progress_thresholds()
        return res

    @api.onchange('commande_id')
    def _onchange_commande_id(self):
        if self.commande_id:
            # Pré-remplir avec le restant à livrer
            self.montant_livre = self.commande_id.montant_restant
            # Optionnel: pré-remplir type paiement si présent sur commande
            if hasattr(self.commande_id, 'type_paiement') and self.commande_id.type_paiement:
                self.type_paiement = self.commande_id.type_paiement in ['cash','bp'] and self.commande_id.type_paiement or 'cash'

class LivraisonSortieStock(models.Model):
    _name = 'pos.livraison.sortie.stock'
    _description = 'Sortie de stock'
    _order = 'date desc'

    name = fields.Char('Référence', required=True, copy=False, readonly=True, default='Nouveau')
    session_id = fields.Many2one('pos.livraison.session', string='Session livraison', required=False, index=True)
    date = fields.Datetime('Date', default=fields.Datetime.now, required=True, index=True)
    motif = fields.Char('Motif', required=True)
    quantite_sacs = fields.Float('Quantité (sacs)', required=True)
    quantite_kg = fields.Float('Quantité (kg)', compute='_compute_quantite_kg', store=True)
    type = fields.Selection([
        ('interne', 'Usage interne'), ('abime', 'Produit abîmé'), ('perte', 'Perte'), ('don', 'Don'), ('autres', 'Autres')
    ], default='interne', string='Type de sortie', required=True, index=True)
    responsable = fields.Char('Responsable')
    notes = fields.Text('Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nouveau') == 'Nouveau':
            vals['name'] = self.env['ir.sequence'].next_by_code('pos.livraison.sortie') or 'Nouveau'
        if not vals.get('session_id'):
            sid = self.env['pos.livraison.session']._ensure_open_for_user(self.env.uid)
            vals['session_id'] = sid
        return super().create(vals)

    @api.depends('quantite_sacs')
    def _compute_quantite_kg(self):
        for rec in self:
            poids_par_sac = float(self.env['ir.config_parameter'].sudo().get_param('pos_livraison.poids_sac', '50'))
            rec.quantite_kg = rec.quantite_sacs * poids_par_sac

class LivraisonQueue(models.Model):
    _name = 'pos.livraison.queue'
    _description = 'File d\'attente des livraisons'

    commande_id = fields.Many2one('pos.caisse.commande', string='Commande', required=True, ondelete='cascade', index=True)
    position = fields.Integer('Position dans la file')
    temps_attente_estime = fields.Float('Temps d\'attente estimé (heures)')
    date_entree_queue = fields.Datetime('Entrée en file', default=fields.Datetime.now, index=True)


class LivraisonSession(models.Model):
    _name = 'pos.livraison.session'
    _description = 'Session de livraison'
    _order = 'date desc'

    name = fields.Char('Nom de la session', required=True, default=lambda self: self._get_default_session_name())
    date = fields.Datetime('Date', default=fields.Datetime.now, required=True)
    date_cloture = fields.Datetime('Date de clôture')
    user_id = fields.Many2one('res.users', string='Livreur', required=True, default=lambda self: self.env.user)
    state = fields.Selection([
        ('ouvert', 'Ouverte'),
        ('ferme', 'Clôturée')
    ], default='ouvert', string='État', required=True, index=True)

    livraison_ids = fields.One2many('pos.livraison.livraison', 'session_id', string='Livraisons')
    sortie_ids = fields.One2many('pos.livraison.sortie.stock', 'session_id', string='Sorties de stock')

    total_livraisons = fields.Integer('Nombre de livraisons', compute='_compute_stats', store=True)
    montant_livre_total = fields.Float('Montant livré total', compute='_compute_stats', store=True)
    sacs_livres_total = fields.Float('Sacs livrés (total)', compute='_compute_stats', store=True)
    sorties_sacs_total = fields.Float('Sacs sortis', compute='_compute_stats', store=True)
    sorties_kg_total = fields.Float('Kg sortis', compute='_compute_stats', store=True)

    def _get_default_session_name(self):
        return f"Livraison-{fields.Datetime.now().strftime('%Y-%m-%d')}"

    @api.model
    def _get_open_for_user(self, uid):
        sess = self.sudo().search([('user_id', '=', uid), ('state', '=', 'ouvert')], order='date desc', limit=1)
        return sess.id if sess else False

    @api.model
    def _ensure_open_for_user(self, uid):
        """Return open session id for user, creating one if necessary."""
        sid = self._get_open_for_user(uid)
        if sid:
            return sid
        sess = self.sudo().create({'user_id': uid, 'state': 'ouvert'})
        return sess.id

    @api.depends('livraison_ids', 'livraison_ids.montant_livre', 'livraison_ids.sacs_farine',
                 'sortie_ids', 'sortie_ids.quantite_sacs', 'sortie_ids.quantite_kg')
    def _compute_stats(self):
        for s in self:
            s.total_livraisons = len(s.livraison_ids)
            s.montant_livre_total = sum(s.livraison_ids.mapped('montant_livre'))
            s.sacs_livres_total = sum(s.livraison_ids.mapped('sacs_farine'))
            s.sorties_sacs_total = sum(s.sortie_ids.mapped('quantite_sacs'))
            s.sorties_kg_total = sum(s.sortie_ids.mapped('quantite_kg'))

    def action_open_session(self):
        self.ensure_one()
        self.state = 'ouvert'
        self.date_cloture = False
        return True

    def action_close_session(self):
        self.ensure_one()
        self.state = 'ferme'
        self.date_cloture = fields.Datetime.now()
        return True
