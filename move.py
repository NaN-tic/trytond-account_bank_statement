# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return (super(Move, cls)._get_origin()
            + ['account.bank.statement'])


class Line(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def _get_origin(cls):
        return (super(Line, cls)._get_origin()
            + ['account.bank.statement.line'])
