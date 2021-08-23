# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.const import OPERATORS
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.modules.currency.fields import Monetary

__all__ = ['AccountBankReconciliation']


class AccountBankReconciliation(ModelView, ModelSQL):
    'Account Bank Reconciliation'
    __name__ = 'account.bank.reconciliation'

    amount = Monetary('Amount', digits='currency', currency='currency',
        required=True)
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    move_line = fields.Many2One('account.move.line', 'Move Line',
        required=True, readonly=True)
    bank_statement_line = fields.Many2One('account.bank.statement.line',
        'Bank Statement Line')

    @classmethod
    def __setup__(cls):
        super(AccountBankReconciliation, cls).__setup__()

    @classmethod
    def write(cls, *args):
        super(AccountBankReconciliation, cls).write(*args)
        actions = iter(args)
        if not Transaction().context.get('from_account_bank_statement_line'):
            for lines, _ in zip(actions, actions):
                move_lines = set([x.move_line for x in lines])
                for move_line in move_lines:
                    move_line.check_bank_lines()

    @classmethod
    def delete(cls, lines):
        if not Transaction().context.get('from_account_bank_statement_line'):
            unallowed = [x for x in lines if x.bank_statement_line]
            if unallowed:
                line = unallowed[0]
                raise UserError(gettext(
                    'account_bank_statement.delete_reconciled',
                        amount=line.amount,
                        statement_line=line.bank_statement_line.rec_name ))

        super(AccountBankReconciliation, cls).delete(lines)

    @classmethod
    def search_domain(cls, domain, active_test=True, tables=None):
        def is_leaf(expression):
            return (isinstance(expression, (list, tuple))
                and len(expression) > 2
                and isinstance(expression[1], str)
                and expression[1] in OPERATORS)  # TODO remove OPERATORS test

        def convert_domain(domain):
            'Replace missing product field by the MoveLine one'
            if is_leaf(domain):
                field = domain[0].split('.', 1)[0]
                if not getattr(cls, field, None):
                    field = 'move_line.' + domain[0]
                    return (field,) + tuple(domain[1:])
                else:
                    return domain
            elif domain in ['OR', 'AND']:
                return domain
            else:
                return [convert_domain(d) for d in domain]
        return super(AccountBankReconciliation, cls).search_domain(
            convert_domain(domain), active_test=active_test, tables=tables)

    @fields.depends('move_line', '_parent_move_line.account')
    def on_change_with_currency(self, name=None):
        if self.move_line and self.move_line.currency:
            return self.move_line.account.company.currency.id
