# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import datetime
import pytz
import csv
from io import StringIO
import decimal
from decimal import Decimal
from trytond.model import Workflow, ModelView, ModelSQL, fields, \
    sequence_ordered
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.pyson import Eval, Not, Equal, If
from trytond.transaction import Transaction
from trytond import backend
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.modules.currency.fields import Monetary

__all__ = ['Statement', 'StatementLine', 'ImportStart', 'Import']

_STATES = {'readonly': Eval('state') != 'draft'}
CONFIRMED_STATES = {
    'readonly': Not(Equal(Eval('state'), 'draft'))
    }
CONFIRMED_DEPENDS = ['state']
POSTED_STATES = {
    'readonly': Not(Equal(Eval('state'), 'confirmed'))
    }
POSTED_DEPENDS = ['state']


class Statement(Workflow, ModelSQL, ModelView):
    'Bank Statement'
    __name__ = 'account.bank.statement'
    company = fields.Many2One('company.company', 'Company', required=True,
        states=_STATES)
    date = fields.DateTime('Date', required=True, states=_STATES,
        help='Created date bank statement')
    start_date = fields.Date('Start Date', required=True,
        states=_STATES, help='Start date bank statement')
    end_date = fields.Date('End Date', required=True,
        states=_STATES, help='End date bank statement')
    start_balance = Monetary('Start Balance', required=True,
        digits='currency', currency='currency',
        states=_STATES)
    end_balance = Monetary('End Balance', required=True,
        digits='currency', currency='currency',
        states=_STATES)
    journal = fields.Many2One('account.bank.statement.journal', 'Journal',
        required=True, domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states=_STATES)
    lines = fields.One2Many('account.bank.statement.line', 'statement',
        'Lines', domain=[
            ('company', '=', Eval('company', -1)),
            ])
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'on_change_with_currency')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', "Cancelled"),
            ], 'State', required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(Statement, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('confirmed', 'cancelled'),
                ('cancelled', 'draft'),
                ('draft', 'cancelled'),
                ))
        cls._buttons.update({
                'confirm': {
                    'invisible': ~Eval('state').in_(['draft']),
                    'icon': 'tryton-forward',
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancelled']),
                    'icon': If(Eval('state') == 'cancelled',
                        'tryton-undo',
                        'tryton-back'),
                    'depends': ['state'],
                    },
                'cancel': {
                    'icon': 'tryton-cancel',
                    'invisible': Eval('state').in_(['cancelled']),
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Statement, cls).__register__(module_name)

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'canceled'))

        # Remove account.bank.reconciliation model
        table_drop = 'account_bank_reconciliation'
        table_h = cls.__table_handler__(module_name)
        exist = table_h.table_exist(table_drop)
        if exist:
            table_h.drop_table('', table_drop)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_date():
        return datetime.now()

    @staticmethod
    def default_start_date():
        return Pool().get('ir.date').today()

    @staticmethod
    def default_end_date():
        return Pool().get('ir.date').today()

    @staticmethod
    def default_start_balance():
        return Decimal(0)

    @fields.depends('journal')
    def on_change_with_currency(self, name=None):
        Company = Pool().get('company.company')

        if self.journal:
            return self.journal.currency.id
        else:
            company = Transaction().context.get('company')
            if company:
                return Company(company).currency.id

    @staticmethod
    def default_end_balance():
        return Decimal(0)

    def get_rec_name(self, name):
        return '%s' % (self.date.strftime("%Y-%m-%d"))

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, statements):
        StatementLine = Pool().get('account.bank.statement.line')
        lines = []
        for statement in statements:
            lines += statement.lines
        StatementLine.confirm(lines)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, statements):
        StatementLine = Pool().get('account.bank.statement.line')
        lines = []
        for statement in statements:
            for line in statement.lines:
                if line.state not in ('draft', 'cancelled'):
                    raise UserError(gettext(
                        'account_bank_statement.cannot_cancel_statement_line',
                            line=line.rec_name,
                            state=line.state))
            lines += statement.lines
        StatementLine.cancel(lines)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, statements):
        StatementLine = Pool().get('account.bank.statement.line')
        lines = []
        for statement in statements:
            lines += statement.lines
        StatementLine.cancel(lines)

    @classmethod
    def delete(cls, statements):
        for statement in statements:
            if statement.lines:
                raise UserError(gettext('account_bank_statement.cannot_delete',
                    statement=statement.rec_name))
        super(Statement, cls).delete(statements)

    @classmethod
    def search_reconcile(cls, statements):
        StatementLine = Pool().get('account.bank.statement.line')

        st_lines = []
        for statement in statements:
            for line in statement.lines:
                st_lines.append(line)

        if st_lines:
            StatementLine.search_reconcile(st_lines)


class StatementLine(sequence_ordered(), Workflow, ModelSQL, ModelView):
    'Bank Statement Line'
    __name__ = 'account.bank.statement.line'
    _rec_name = 'description'

    statement = fields.Many2One('account.bank.statement', 'Statement',
        required=True, domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states=CONFIRMED_STATES)
    company = fields.Many2One('company.company', 'Company', required=True,
        states=CONFIRMED_STATES)
    date = fields.Function(fields.DateTime('Date', required=True),
        'get_date_utc', searcher='search_date_utc', setter='set_date_utc')
    date_utc = fields.DateTime('Date UTC', states=CONFIRMED_STATES)
    description = fields.Char('Description', required=True,
        states=CONFIRMED_STATES)
    notes = fields.Char('Notes', states=POSTED_STATES)
    amount = Monetary('Amount', digits='company_currency',
        currency='statement_currency', required=True, states=CONFIRMED_STATES)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', "Cancelled"),
            ('posted', 'Posted'),
            ], 'State', required=True, readonly=True)
    account = fields.Function(fields.Many2One('account.account',
            'Account'), 'get_account')
    reconciled = fields.Function(fields.Boolean('Reconciled'),
        'get_accounting_vals')
    moves_amount = fields.Function(Monetary('Moves Amount',
            digits='company_currency', currency='company_currency'),
            'on_change_with_moves_amount')
    journal = fields.Function(fields.Many2One('account.bank.statement.journal',
            'Journal'), 'get_journal', searcher='search_journal')
    statement_currency = fields.Function(fields.Many2One('currency.currency',
            'Statement Currency'),
            'on_change_with_statement_currency')
    company_currency = fields.Function(fields.Many2One('currency.currency',
            'Company Currency'),
            'on_change_with_company_currency')
    company_moves_amount = fields.Function(Monetary('Moves Amount',
            digits='company_currency', currency='company_currency'),
            'get_accounting_vals')
    company_amount = fields.Function(Monetary('Company Amount',
            digits='company_currency', currency='company_currency'),
            'get_accounting_vals')

    @classmethod
    def __setup__(cls):
        super(StatementLine, cls).__setup__()
        cls._order.insert(0, ('date_utc', 'ASC'))
        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('confirmed', 'posted'),
                ('cancelled', 'draft'),
                ('draft', 'cancelled'),
                ('confirmed', 'cancelled'),
                ('posted', 'cancelled'),
                ))
        cls._buttons.update({
                'confirm': {
                    'invisible': ~Eval('state').in_(['draft']),
                    'icon': 'tryton-forward',
                    },
                'post': {
                    'invisible': Eval('state').in_([
                            'draft', 'cancelled', 'posted']),
                    'icon': 'tryton-ok',
                    },
                'cancel': {
                    'icon': 'tryton-cancel',
                    'invisible': Eval('state').in_(['cancelled']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancelled']),
                    'icon': If(Eval('state') == 'cancelled',
                        'tryton-undo',
                        'tryton-back'),
                    'depends': ['state'],
                    },
                'search_reconcile': {
                    'invisible': ~Eval('state').in_(['confirmed']),
                    'icon': 'tryton-launch',
                    },
                })
        cls.__rpc__.update({
                'post': RPC(
                    readonly=False, instantiate=0, fresh_session=True),
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = backend.TableHandler(cls, module_name)
        sql_table = cls.__table__()

        # Migration: rename date into date_utc
        if (table.column_exist('date')
                and not table.column_exist('date_utc')):
            table.not_null_action('date', 'remove')
            table.column_rename('date', 'date_utc')

        super(StatementLine, cls).__register__(module_name)

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'canceled'))

    @classmethod
    def get_date_utc(cls, lines, names):
        # get date + UTC
        result = {}
        for name in names:
            result[name] = dict((x.id, None) for x in lines)

        for line in lines:
            for name in names:
                line_date = getattr(line, name + '_utc')
                if (line_date and line.statement
                        and line.statement.company.timezone):
                    timezone = pytz.timezone(line.statement.company.timezone)
                    date = timezone.localize(line_date)
                    line_date += date.utcoffset()
                result[name][line.id] = line_date
        return result

    @classmethod
    def search_date_utc(cls, name, clause):
        return [(name + '_utc',) + tuple(clause[1:])]

    @classmethod
    def set_date_utc(cls, lines, name, value):
        if not value:
            return

        # set date to UTC
        timezone = None
        for line in lines:
            if (line.statement and line.statement.company
                    and line.statement.company.timezone):
                timezone = line.statement.company.timezone
                break
        if timezone and isinstance(value, datetime):
            timezone = pytz.timezone(timezone)
            date = timezone.localize(value)
            value -= date.utcoffset()

        cls.write(lines, {
            name + '_utc': value,
            })

    def _search_reconciliation(self):
        pass

    @classmethod
    @ModelView.button
    def search_reconcile(cls, st_lines):
        for st_line in st_lines:
            st_line._search_reconciliation()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_date():
        return datetime.now()

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('statement', '_parent_statement.journal')
    def on_change_with_statement_currency(self, name=None):
        if self.statement and self.statement.journal:
            return self.statement.journal.currency.id

    @fields.depends('statement', '_parent_statement.company')
    def on_change_with_company_currency(self, name=None):
        if self.statement and self.statement.company:
            return self.statement.company.currency.id

    def get_account(self, name):
        account = self.statement.journal.account
        return account and account.id

    @classmethod
    def get_accounting_vals(cls, lines, names):
        res = {}
        line_ids = [x.id for x in lines]
        for name in names:
            value = False if name == 'reconciled' else Decimal(0)
            res[name] = {}.fromkeys(line_ids, value)

        Currency = Pool().get('currency.currency')
        for line in lines:
            amount = line.company_currency.round(line.moves_amount)
            company_amount = line.company_currency.round(line.amount)
            if line.statement_currency != line.company_currency:
                with Transaction().set_context(date=line.date.date()):
                    company_amount = Currency.compute(
                        line.statement_currency, company_amount,
                        line.company_currency)
            if 'company_amount' in names:
                res['company_amount'][line.id] = company_amount
            if 'reconciled' in names:
                res['reconciled'][line.id] = (amount == company_amount)
        return res

    @fields.depends('company_currency')
    def on_change_with_moves_amount(self, name=None):
        return Decimal(0)

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, lines):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, lines):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, lines):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, lines):
        with Transaction().set_context(from_account_bank_statement_line=True):
            cls.write(lines, {
                'state': 'cancelled',
                })

    @classmethod
    def validate(cls, lines):
        for line in lines:
            line.check_amounts()

    def check_amounts(self):
        if self.state == 'posted' and self.company_amount != self.moves_amount:
            raise UserError(gettext(
                'account_bank_statement.different_amounts',
                    moves_amount=self.moves_amount,
                    amount=self.company_amount,
                    line=self.rec_name))

    def get_journal(self, name):
        return self.statement.journal.id

    @classmethod
    def search_journal(cls, name, clause):
        return [('statement.journal',) + tuple(clause[1:])]

    @classmethod
    def search(cls, args, offset=0, limit=None, order=None, count=False,
            query=False):
        """
        Override default search function so that if the user sorts by one field
        only, then 'sequence' is always added as a second sort field. This is
        specially important when the user sorts by date (the most usual) to
        ensure all moves from the same date are properly sorted.
        """
        if order is None:
            order = cls._order
        order = list(order)
        if len(order) == 1:
            order.append(('sequence', order[0][1]))
        return super(StatementLine, cls).search(args, offset, limit, order,
            count, query)

    @classmethod
    def delete(cls, lines):
        for line in lines:
            if line.state not in ('draft', 'cancelled'):
                raise UserError(gettext(
                    'account_bank_statement.cannot_delete_statement_line',
                        line=line.rec_name))
        super(StatementLine, cls).delete(lines)


class ImportStart(ModelView):
    'Import Start'
    __name__ = 'account.bank.statement.import.start'
    import_file = fields.Binary('File', required=True)
    type = fields.Selection([
            ('csv', 'CSV (date, description, amount)'),
            ], 'Type', required=True)
    attachment = fields.Boolean('Attach file after import')
    confirm = fields.Boolean('Confirm',
        help='Confirm Bank Statement after import.')

    @classmethod
    def default_attachment(cls):
        return True

    @classmethod
    def default_confirm(cls):
        return True


class Import(Wizard):
    'Import'
    __name__ = 'account.bank.statement.import'
    start = StateView('account.bank.statement.import.start',
        'account_bank_statement.import_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Import File', 'import_file', 'tryton-ok', default=True),
            ])
    import_file = StateTransition()

    def transition_import_file(self):
        pool = Pool()
        BankStatement = pool.get('account.bank.statement')
        Attachment = pool.get('ir.attachment')

        active_id = Transaction().context['active_id']
        if not active_id:
            return 'end'

        statement = BankStatement(active_id)
        if statement.lines:
            raise UserError(
                gettext('account_bank_statement.account_bank_statement_already_has_lines',
                    statement=statement.rec_name))

        self.process(statement)

        if self.start.confirm:
            BankStatement.confirm([statement])
            BankStatement.search_reconcile([statement])

        if self.start.attachment:
            attach = Attachment(
                name=datetime.now().strftime("%y/%m/%d %H:%M:%S"),
                type='data',
                data=self.start.import_file,
                resource=str(statement))
            attach.save()
        return 'end'

    def process(self, statement):
        if self.start.type != 'csv':
            return
        BankStatementLine = Pool().get('account.bank.statement.line')

        try:
            csv_file = StringIO(self.start.import_file.decode('utf-8'))
        except csv.Error as e:
            raise UserError(gettext('account_bank_statement.format_error',
                error=str(e)))
        except UnicodeDecodeError:
            raise UserError(gettext('account_bank_statement.unicode_error'))

        try:
            reader = csv.reader(csv_file)
        except csv.Error as e:
            raise UserError(gettext('account_bank_statement.format_error',
                error=str(e)))

        count = 0
        lines = []
        for record in reader:
            count += 1
            if len(record) < 3:
                raise UserError(gettext(
                    'account_bank_statement.missing_columns',
                    columns=str(count)))
            line = BankStatementLine()
            line.statement = statement
            line.date = self.string_to_date(record[0])
            line.description = record[1] or ''
            line.amount = self.string_to_number(record[2])
            lines.append(line)
        BankStatementLine.save(lines)

    def string_to_date(self, text, patterns=('%d/%m/%Y', '%Y-%m-%d')):
        for pattern in patterns:
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue
        raise UserError(gettext('account_bank_statement.invalid_date',
            date=text))

    def string_to_number(self, text, decimal_separator='.',
            thousands_separator=','):
        text = text.replace(thousands_separator, '')
        if decimal_separator != '.':
            text = text.replace(decimal_separator, '.')
        try:
            return Decimal(text)
        except (ValueError, decimal.InvalidOperation):
            raise UserError(gettext('account_bank_statement.invalid_number',
                number=text))
