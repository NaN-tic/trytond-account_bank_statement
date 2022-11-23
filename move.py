# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta


class Line(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def _get_origin(cls):
        return (super(Line, cls)._get_origin()
            + ['account.bank.statement.line'])
