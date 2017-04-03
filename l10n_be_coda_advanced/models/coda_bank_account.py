# -*- coding: utf-8 -*-
# Copyright 2009-2016 Noviat.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from openerp import api, fields, models, _
from openerp.exceptions import ValidationError


class CodaBankAccount(models.Model):
    _name = 'coda.bank.account'
    _description = 'CODA Bank Account Configuration'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    bank_id = fields.Many2one(
        'res.partner.bank', string='Bank Account', required=True,
        help="Bank Account Number.\nThe CODA import function will "
             "find its CODA processing parameters on this number.")
    description1 = fields.Char(
        string='Primary Account Description', size=35,
        help="The Primary or Secondary Account Description should match "
             "the corresponding Account Description in the CODA file.")
    description2 = fields.Char(
        string='Secondary Account Description', size=35,
        help="The Primary or Secondary Account Description should match "
             "the corresponding Account Description in the CODA file.")
    state = fields.Selection(
        [('normal', 'Normal'),
         ('skip', 'Skip'),
         ('info', 'Info')],
        string='Type', required=True,
        default='normal',
        help="No Bank Statements will be generated for "
             "CODA Bank Statements from Bank Accounts of "
             "type 'Info' and 'Skip'."
             "Type 'Info' Statements will be parsed and can be consulted "
             "via the 'CODA Bank Statements' menu.")
    journal_id = fields.Many2one(
        'account.journal', string='Journal',
        domain=[('type', '=', 'bank')],
        states={'normal': [('required', True)],
                'info': [('required', False)]},
        help='Bank Journal for the Bank Statement')
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.user.company_id.currency_id,
        help='The currency of the CODA Bank Statement')
    coda_st_naming = fields.Char(
        string='Bank Statement Naming Policy', size=64,
        default='%(code)s-%(y)s-%(coda)s',
        help="Define the rules to create the name of the Bank Statements "
             "generated by the CODA processing."
             "\nE.g. %(code)s%(y)s/%(paper)s"
             "\n\nVariables:"
             "\nBank Journal Code: %(code)s"
             "\nYear (of CODA 'New Balance Date') with Century: %(year)s"
             "\nYear (of CODA 'New Balance Date') without Century: %(y)s"
             "\nCODA sequence number: %(coda)s"
             "\nPaper Statement sequence number "
             "(as specified on 'Old Balance' record): %(paper_ob)s"
             "\nPaper Statement sequence number "
             "(as specified on 'New Balance' record): %(paper)s")
    transfer_account = fields.Many2one(
        'account.account', string='Default Internal Transfer Account',
        domain=[('code', 'like', '58%'), ('type', '!=', 'view')],
        required=True,
        help="Set here the default account that will be used for "
             "internal transfer between own bank accounts "
             "(e.g. transfer between current and deposit bank accounts).")
    account_mapping_ids = fields.One2many(
        'coda.account.mapping.rule', 'coda_bank_account_id',
        string='Account Mapping Rules')
    find_bbacom = fields.Boolean(
        string="Lookup Structured Communication of type 'BBA'",
        default=True,
        help="Partner lookup and reconciliation "
             "via the 'BBA' Structured Communication."
             "'\nA partial reconciliation will be created when there is "
             "no exact match between the Invoice "
             "and Bank Transaction amounts.")
    find_inv_number = fields.Boolean(
        string='Lookup Invoice Number',
        default=True,
        help="Partner lookup and reconciliation via the Invoice Number "
             "when a communication in free format is used."
             "\nA reconciliation will only be created in case of "
             "exact match between the Invoice and "
             "Bank Transaction amounts.")
    find_account_move_line = fields.Boolean(
        string='Lookup Accounting Entries',
        default=False,   # default = False since this lookup may burn resources
        help="Find matching accounting entry when previous lookups "
             "(payment order, invoice, sales order) have failed."
             "\nThis allows e.g. to match with manually encoded "
             "accounting entries (journal item 'name' field combined "
             "exact match on amount) or non payable/receivable entries.")
    find_partner = fields.Boolean(
        string='Lookup Partner',
        default=True,
        help="Partner lookup via Bank Account Number "
             "in order to facilitate the reconciliation.")
    update_partner = fields.Boolean(
        string='Update Partner Bank Accounts',
        default=True,
        help="Update Partner record when the Counterparty's Bank Account "
             "has not been registered yet.")
    balance_start_enforce = fields.Boolean(
        string='Prevent invalid Opening Balances',
        default=True,
        help="Do not process Statements with an Opening Balance that "
             "doesn't match the previous Closing Balance.")
    discard_dup = fields.Boolean(
        string='Discard Duplicates',
        help="Duplicate Bank Statements will be discarded. "
             "Select the corresponding 'CODA Bank Statement' in order "
             "to view the contents of such duplicates.")
    active = fields.Boolean(
        string='Active', default=True,
        help="If the active field is set to False, "
             "it will allow you to hide the "
             "CODA Bank Account Configuration without removing it.")
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.user.company_id,
        required=True)
    display_name = fields.Char(
        compute='_compute_display_name', string="Display Name",
        store=True, readonly=True)

    @api.one
    @api.depends('bank_id', 'currency_id', 'description1')
    def _compute_display_name(self):
        display_name = self.bank_id.acc_number \
            + ' (' + self.currency_id.name + ')'
        if self.description1:
            display_name += ' ' + self.description1
        self.display_name = len(display_name) > 55 \
            and display_name[:55] + '...' \
            or display_name

    _sql_constraints = [
        ('account_uniq_1', 'unique (bank_id, description1, currency_id)',
         "The combination of Bank Account, Account Description "
         "and Currency must be unique !"),
        ('account_uniq_2', 'unique (bank_id, description2, currency_id)',
         "The combination of Bank Account, Account Description "
         "and Currency must be unique !"),
    ]

    @api.one
    @api.constrains('currency_id', 'journal_id')
    def _check_currency(self):
        if (self.state == 'normal') and self.journal_id:
            c1 = self.journal_id.currency \
                and self.currency_id != self.journal_id.currency
            c2 = not self.journal_id.currency \
                and self.currency_id != self.company_id.currency_id
            if c1 or c2:
                raise ValidationError(_(
                    "Configuration Error!"
                    "\nThe Bank Account Currency should match "
                    "the Journal Currency !"))

    @api.one
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = {} if default is None else default.copy()
        default.update({
            'journal_id': False,
            'name': (self.name or '') + ' (copy)',
            'description1': (self.description1 or '') + ' (copy)',
            'description2': (self.description2 or '') + ' (copy)',
            'state': self.state,
            })
        return super(CodaBankAccount, self).copy(default)


class CodaAccountMappingRule(models.Model):
    _name = 'coda.account.mapping.rule'
    _description = 'Rules Engine to assign accounts during CODA parsing'
    _order = 'sequence'

    coda_bank_account_id = fields.Many2one(
        'coda.bank.account', string='CODA Bank Account', ondelete='cascade')
    sequence = fields.Integer(
        string='Sequence', default=10,
        help='Determines the order of the rules to assign accounts')
    name = fields.Char(string='Rule Name', required=True)
    active = fields.Boolean(
        string='Active', default=True, help='Switch on/off this rule.')
    # matching criteria
    trans_type_id = fields.Many2one(
        'account.coda.trans.type', string='Transaction Type')
    trans_family_id = fields.Many2one(
        'account.coda.trans.code', string='Transaction Family',
        domain=[('type', '=', 'family')])
    trans_code_id = fields.Many2one(
        'account.coda.trans.code', 'Transaction Code',
        domain=[('type', '=', 'code')])
    trans_category_id = fields.Many2one(
        'account.coda.trans.category', string='Transaction Category')
    partner_id = fields.Many2one(
        'res.partner', string='Partner', ondelete='cascade',
        domain=['|', ('parent_id', '=', False), ('is_company', '=', True)])
    freecomm = fields.Char(string='Free Communication', size=128)
    struct_comm_type_id = fields.Many2one(
        'account.coda.comm.type', string='Structured Communication Type')
    structcomm = fields.Char(string='Structured Communication', size=128)
    payment_reference = fields.Char(
        string='Payment Reference', size=35,
        help="Payment Reference. For SEPA (SCT or SDD) transactions, "
             "the EndToEndReference is recorded in this field.")
    # results
    account_id = fields.Many2one(
        'account.account', string='Account', ondelete='cascade',
        required=True, domain=[('type', '!=', 'view')])
    tax_code_id = fields.Many2one(
        'account.tax.code', string='Tax Case', ondelete='cascade')
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        ondelete='set null',
        domain=[('type', '!=', 'view'),
                ('state', 'not in', ('close', 'cancelled'))])

    def _rule_select_extra(self, coda_bank_account_id):
        """
        Use this method to customize the mapping rule engine.
        Cf. l10n_be_coda_analytic_plan module for an example.
        """
        return ''

    def _rule_result_extra(self, coda_bank_account_id):
        """
        Use this method to customize the mapping rule engine.
        Cf. l10n_be_coda_analytic_plan module for an example.
        """
        return []

    @api.model
    def rule_get(self, coda_bank_account_id,
                 trans_type_id=None, trans_family_id=None,
                 trans_code_id=None, trans_category_id=None,
                 struct_comm_type_id=None, partner_id=None,
                 freecomm=None, structcomm=None, payment_reference=None):

        select = \
            'SELECT trans_type_id, trans_family_id, trans_code_id, ' \
            'trans_category_id, ' \
            'struct_comm_type_id, partner_id, freecomm, structcomm, ' \
            'account_id, tax_code_id, analytic_account_id, payment_reference'
        select += self._rule_select_extra(coda_bank_account_id) + ' '
        select += \
            "FROM coda_account_mapping_rule " \
            "WHERE active = TRUE AND coda_bank_account_id = %s " \
            "ORDER BY sequence" % coda_bank_account_id
        self._cr.execute(select)
        rules = self._cr.dictfetchall()
        condition = \
            "(not rule['trans_type_id'] or " \
            "(trans_type_id == rule['trans_type_id'])) and " \
            "(not rule['trans_family_id'] or " \
            "(trans_family_id == rule['trans_family_id'])) " \
            "and (not rule['trans_code_id'] or " \
            "(trans_code_id == rule['trans_code_id'])) and " \
            "(not rule['trans_category_id'] or " \
            "(trans_category_id == rule['trans_category_id'])) " \
            "and (not rule['struct_comm_type_id'] or " \
            "(struct_comm_type_id == rule['struct_comm_type_id'])) and " \
            "(not rule['partner_id'] or " \
            "(partner_id == rule['partner_id'])) " \
            "and (not rule['freecomm'] or (rule['freecomm'].lower() in " \
            "(freecomm and freecomm.lower() or ''))) " \
            "and (not rule['structcomm'] or " \
            "(rule['structcomm'] in (structcomm or ''))) " \
            "and (not rule['payment_reference'] or " \
            "(rule['payment_reference'] in (payment_reference or ''))) "
        result_fields = [
            'account_id', 'tax_code_id', 'analytic_account_id']
        result_fields += self._rule_result_extra(coda_bank_account_id)
        res = {}
        for rule in rules:
            if eval(condition):
                for f in result_fields:
                    res[f] = rule[f]
                break
        return res
