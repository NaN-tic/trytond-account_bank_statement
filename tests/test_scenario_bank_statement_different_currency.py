# =======================================================
# Account Bank Statement With Different Currency Scenario
# =======================================================

# Imports
from trytond.modules.account.tests.tools import create_fiscalyear, create_chart, get_accounts
from trytond.modules.company.tests.tools import create_company, get_company 
from trytond.modules.currency.tests.tools import get_currency 
from trytond.tests.tools import activate_modules 
from proteus import Model
from decimal import Decimal 
import datetime 
import unittest
from trytond.tests.test_tryton import drop_db

class Test(unittest.TestCase):
    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        today = datetime.date.today()
        now = datetime.datetime.now()

        # Install account_bank_statement and account_invoice
        config = activate_modules('account_bank_statement')

        # Create company
        dolar = get_currency('USD')
        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()

        # Reload the context
        User = Model.get('res.user')

        # Create fiscal year
        fiscalyear = create_fiscalyear(company)
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        receivable = accounts['receivable']
        revenue = accounts['revenue']
        expense = accounts['expense']
        cash = accounts['cash']
        cash.bank_reconcile = True
        cash.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        # Create Journal
        Sequence = Model.get('ir.sequence')
        SequenceType = Model.get('ir.sequence.type')
        sequence_type, = SequenceType.find([('name', '=', 'Account Journal')])
        sequence = Sequence(name='Bank', sequence_type=sequence_type,
            company=company)
        sequence.save()
        AccountJournal = Model.get('account.journal')
        account_journal = AccountJournal(name='Statement',
            type='cash',
            sequence=sequence)
        account_journal.save()

        # Create Dollar Statement Journal
        StatementJournal = Model.get('account.bank.statement.journal')
        statement_journal_dolar = StatementJournal(name='Test',
            journal=account_journal, currency=dolar, account=cash)
        statement_journal_dolar.save()

        # Create Euro Statement Journal
        statement_journal_eur = StatementJournal(name='Test',
            journal=account_journal, currency=eur, account=cash)
        statement_journal_eur.save()

        # Create Bank Move
        period = fiscalyear.periods[0]
        Move = Model.get('account.move')
        move = Move()
        move.period = period
        move.journal = account_journal
        move.date = period.start_date
        line = move.lines.new()
        line.account = cash
        line.debit = Decimal('80.0')
        line2 = move.lines.new()
        line2.account = receivable
        line2.credit = Decimal('80.0')
        line2.party = party
        move.click('post')
        self.assertEqual(move.state
        , 'posted'
        )

        # Create Bank Statement With Different Curreny
        BankStatement = Model.get('account.bank.statement')
        statement = BankStatement(journal=statement_journal_dolar, date=now)

        # Create Bank Statement Lines
        StatementLine = Model.get('account.bank.statement.line')
        statement_line = StatementLine()
        statement.lines.append(statement_line)
        statement_line.date = now
        statement_line.description = 'Statement Line'
        statement_line.amount = Decimal('80.0') / Decimal('2.0')
        statement.click('confirm')
        self.assertEqual(statement.state
        , 'confirmed'
        )
        statement_line = StatementLine(1)
        self.assertEqual(statement_line.state
        , 'confirmed'
        )

        # Cancel line
        statement_line.click('cancel')
        self.assertEqual(statement_line.state
        , 'cancelled'
        )