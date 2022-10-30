#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from trytond.pool import Pool
from . import statement
from . import move
from . import account
from . import journal


def register():
    Pool.register(
        journal.BankJournal,
        statement.Statement,
        statement.StatementLine,
        statement.ImportStart,
        move.Line,
        account.AccountTemplate,
        account.Account,
        move.OpenBankReconcileLinesStart,
        module='account_bank_statement', type_='model')
    Pool.register(
        statement.Import,
        move.OpenBankReconcileLines,
        module='account_bank_statement', type_='wizard')
