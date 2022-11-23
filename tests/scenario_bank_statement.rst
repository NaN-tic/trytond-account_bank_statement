===============================
Account Bank Statement Scenario
===============================

Imports::

    >>> import datetime
    >>> import pytz
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> today = datetime.date.today()
    >>> now = datetime.datetime.now()

Install account_bank_statement::

    >>> config = activate_modules('account_bank_statement')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> company.timezone = 'Europe/Madrid'
    >>> company.save()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']
    >>> cash.bank_reconcile = True
    >>> cash.save()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create Journal::

    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> sequence_type, = SequenceType.find([('name', '=', 'Account Journal')])
    >>> sequence = Sequence(name='Bank', sequence_type=sequence_type,
    ...     company=company)
    >>> sequence.save()
    >>> AccountJournal = Model.get('account.journal')
    >>> account_journal = AccountJournal(name='Statement',
    ...     type='cash',
    ...     sequence=sequence)
    >>> account_journal.save()

Create Statement Journal::

    >>> StatementJournal = Model.get('account.bank.statement.journal')
    >>> statement_journal = StatementJournal(name='Test',
    ...     journal=account_journal, currency=company.currency, account=cash)
    >>> statement_journal.save()

Create Bank Move::

    >>> period = fiscalyear.periods[0]
    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = account_journal
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.credit = Decimal('80.0')
    >>> line2 = move.lines.new()
    >>> line2.account = receivable
    >>> line2.debit = Decimal('80.0')
    >>> line2.party = party
    >>> move.click('post')
    >>> move.state
    'posted'

Create Bank Statement With Different Curreny::

    >>> BankStatement = Model.get('account.bank.statement')
    >>> statement = BankStatement(journal=statement_journal, date=now)

Create Bank Statement Lines::

    >>> StatementLine = Model.get('account.bank.statement.line')
    >>> statement_line = StatementLine()
    >>> statement.lines.append(statement_line)
    >>> statement_line.date = now
    >>> statement_line.description = 'Statement Line'
    >>> statement_line.amount = Decimal('80.0')
    >>> statement.click('confirm')
    >>> statement.state
    'confirmed'
    >>> statement_line = StatementLine(1)
    >>> statement_line.state
    'confirmed'
    >>> statement_line.date_utc != statement_line.date
    True
    >>> timezone = pytz.timezone('Europe/Madrid')
    >>> date = timezone.localize(statement_line.date_utc)
    >>> line_date = statement_line.date_utc + date.utcoffset()
    >>> statement_line.date == line_date
    True

Cancel line::

    >>> statement_line.click('cancel')
    >>> statement_line.state
    'cancelled'
