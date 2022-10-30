# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from sql.conditionals import Coalesce
from sql.aggregate import Sum

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, PYSONEncoder
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.i18n import gettext
from trytond.exceptions import UserError
from sql import Null

_ZERO = Decimal('0.00')


class Line(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    bank_amount = fields.Function(fields.Numeric('Bank Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_bank_amounts')
    unreconciled_amount = fields.Function(fields.Numeric('Unreconciled Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
            'get_bank_amounts')
    bank_reconciled = fields.Function(fields.Boolean('Bank Reconciled'),
            'get_bank_amounts', searcher='search_bank_reconciled')

    @classmethod
    def search_bank_reconciled(cls, name, clause):
        # TODO: Review!!
        pass

    @classmethod
    def _get_origin(cls):
        return (super(Line, cls)._get_origin()
            + ['account.bank.statement.line'])

    def get_bank_amounts(cls, lines, names):
        res = {}
        all_names = ('bank_amount', 'unreconciled_amount', 'bank_reconciled')
        for name in all_names:
            res[name] = {}.fromkeys([x.id for x in lines], 0)

        for line in lines:
            if 'bank_reconciled' in names:
                res['bank_reconciled'][line.id] = False
                if res['unreconciled_amount'][line.id] == _ZERO:
                    res['bank_reconciled'][line.id] = True
        for name in all_names:
            if name not in names:
                del res[name]
        return res

    def on_change_with_bank_amount(self):
        # TODO: Review!!
        pass

    def on_change_with_unreconciled_amount(self):
        # TODO: Review!!
        pass


class OpenBankReconcileLinesStart(ModelView):
    'Open Bank Reconcile Lines (Start)'
    __name__ = 'account.move.open_bank_reconcile_lines.start'

    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[('type', '!=', Null), ('bank_reconcile', '=', True)])


class OpenBankReconcileLines(Wizard):
    'Open Bank Reconcile Lines'
    __name__ = 'account.move.open_bank_reconcile_lines'

    start = StateView('account.move.open_bank_reconcile_lines.start',
        'account_bank_statement.open_reconcile_bank_lines_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction(
        'account_bank_statement.act_move_line_bank_reconcile_form')

    def do_open_(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([
                ('account', '=', self.start.account.id)])
        return action, {}
