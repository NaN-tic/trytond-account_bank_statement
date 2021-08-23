# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from sql.conditionals import Coalesce
from sql.aggregate import Sum

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import PYSONEncoder
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.modules.currency.fields import Monetary
from sql import Null


__all__ = ['Line', 'Move', 'OpenBankReconcileLines',
    'OpenBankReconcileLinesStart']

_ZERO = Decimal('0.00')


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def post(cls, moves):
        res = super(Move, cls).post(moves)
        BankMove = Pool().get('account.bank.reconciliation')
        bank_moves = []
        for move in moves:
            for line in move.lines:
                if line.account.bank_reconcile:
                    bank_move = {
                        'amount': line.debit - line.credit,
                        'move_line': line
                        }
                    bank_moves.append(bank_move)
        BankMove.create(bank_moves)
        return res


class Line(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    bank_lines = fields.One2Many('account.bank.reconciliation', 'move_line',
        'Conciliation Lines', readonly=True)
    bank_amount = fields.Function(Monetary('Bank Amount',
            currency='currency', digits='currency'),
            'get_bank_amounts')
    unreconciled_amount = fields.Function(Monetary('Unreconciled Amount',
            currency='currency', digits='currency'),
            'get_bank_amounts')
    bank_reconciled = fields.Function(fields.Boolean('Bank Reconciled'),
            'get_bank_amounts', searcher='search_bank_reconciled')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._check_modify_exclude.add('bank_lines')

    @classmethod
    def search_bank_reconciled(cls, name, clause):
        pool = Pool()
        BankReconcile = pool.get('account.bank.reconciliation')
        move = cls.__table__()
        bank_reconcile = BankReconcile.__table__()
        subquery = bank_reconcile.select(bank_reconcile.move_line,
            Sum(Coalesce(bank_reconcile.amount, 0)).as_('reconciled'),
            group_by=bank_reconcile.move_line)
        Operator = fields.SQL_OPERATORS[clause[1]]
        query = move.join(subquery, type_='LEFT', condition=(
            subquery.move_line == move.id)).select(move.id,
                where=(Operator((
                    (Coalesce(subquery.reconciled, 0) ==
                      (move.debit - move.credit))),
                        clause[2])
                ))
        return [('id', 'in', query)]

    @classmethod
    def _get_origin(cls):
        return (super(Line, cls)._get_origin()
            + ['account.bank.statement.line'])

    @classmethod
    def delete(cls, lines):
        for line in lines:
            for bank_line in line.bank_lines:
                if bank_line.bank_statement_line:
                    raise UserError(gettext(
                        'account_bank_statement.line_reconciled',
                        line=line.rec_name,
                        statement_line=bank_line.bank_statement_line.rec_name,
                        amount=bank_line.amount))
        super(Line, cls).delete(lines)

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default['bank_lines'] = None
        return super(Line, cls).copy(lines, default=default)

    def check_bank_lines(self):
        BankLine = Pool().get('account.bank.reconciliation')
        if self.bank_amount != self.debit - self.credit:
            bank_lines = [x for x in self.bank_lines
                if not x.bank_statement_line]
            BankLine.delete(bank_lines)
            bank_line = BankLine()
            bank_line.amount = (self.debit - self.credit) - self.bank_amount
            bank_line.move_line = self
            bank_line.save()

    @classmethod
    def get_bank_amounts(cls, lines, names):
        res = {}
        all_names = ('bank_amount', 'unreconciled_amount', 'bank_reconciled')
        for name in all_names:
            res[name] = {}.fromkeys([x.id for x in lines], 0)

        for line in lines:
            for bank_line in line.bank_lines:
                if 'bank_amount' in names and bank_line.bank_statement_line:
                    res['bank_amount'][line.id] += bank_line.amount
                if 'unreconciled_amount' in names and \
                        not bank_line.bank_statement_line:
                    res['unreconciled_amount'][line.id] += bank_line.amount

            if not line.bank_lines:
                res['unreconciled_amount'][line.id] = line.debit or line.credit

            if 'bank_reconciled' in names:
                res['bank_reconciled'][line.id] = False
                if res['unreconciled_amount'][line.id] == _ZERO:
                    res['bank_reconciled'][line.id] = True
        for name in all_names:
            if name not in names:
                del res[name]
        return res

    @fields.depends('bank_lines')
    def on_change_with_bank_amount(self):
        amount = Decimal('0.0')
        for line in self.bank_lines:
            if line.bank_statement_line:
                amount += line.amount
        return amount

    @fields.depends('bank_lines')
    def on_change_with_unreconciled_amount(self):
        amount = Decimal('0.0')
        for line in self.bank_lines:
            if not line.bank_statement_line and line.amount:
                amount += line.amount
        return amount


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
