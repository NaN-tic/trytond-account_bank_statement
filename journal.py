# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['BankJournal']


class BankJournal(ModelSQL, ModelView):
    'Bank Statement Journal'
    __name__ = 'account.bank.statement.journal'
    name = fields.Char('Name', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        domain=[
            ('type', '=', 'cash'),
            ],
        context={
            'company': Eval('company'),
            },
        depends=['company'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    account = fields.Many2One('account.account', "Account", required=True,
        domain=[
            ('bank_reconcile', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])

    @staticmethod
    def default_currency():
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def write(cls, journals, values, *args):
        Statement = Pool().get('account.bank.statement')
        actions = iter((journals, values) + args)
        args = []
        for journals, values in zip(actions, actions):
            if 'currency' not in values:
                super(BankJournal, cls).write(journals, values)
                continue

            for journal in journals:
                statements = Statement.search([('journal', '=', journal),
                    ('state', 'in', ['confirmed', 'posted'])], limit=1)
                if not statements:
                    continue
                statement, = statements
                raise UserError(gettext(
                    'account_bank_statement.currency_modify',
                        date=statement.date))
            args.extend((journals, values))

        super(BankJournal, cls).write(journals, values, *args)
