"""Explicit accounting relations; zero residual is not business acceptance."""
from decimal import Decimal, ROUND_HALF_UP, localcontext

YI = Decimal('100000000')


def decimal_text(value):
    return '' if value is None else format(value, 'f')


def display_yi(value, places=4):
    with localcontext() as ctx:
        ctx.prec = 256
        return decimal_text((value / YI).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def growth(base, current):
    if base is None or current is None:
        return None, 'missing_or_conflicting_input'
    if base <= 0:
        return None, 'nonpositive_base'
    if current < 0:
        return None, 'sign_crossing'
    with localcontext() as ctx:
        ctx.prec = 50
        return (current-base)/base, 'ordinary_yoy'


def bridge(values, target, terms, relation_status):
    """values maps IDs to (base, current); terms contain unique (ID, sign)."""
    ids = [key for key, sign in terms]
    if len(ids) != len(set(ids)) or target in ids:
        raise ValueError('桥接不得重复项目或把目标本身作为组成项目')
    if any(sign not in (-1, 1) for _, sign in terms):
        raise ValueError('桥接符号必须是 +1 或 -1')
    result = dict(target=target, terms=terms, relation_status=relation_status,
                  business_status='待金融组确认', tolerance=None,
                  residual_definition='reported_target - sum(signed_components)')
    with localcontext() as ctx:
        ctx.prec = 256
        for index, period in enumerate(('base', 'current')):
            missing = [key for key in [target, *ids] if key not in values or values[key][index] is None]
            calculated = None if missing else sum((values[key][index]*sign for key, sign in terms), Decimal(0))
            actual = values.get(target, (None, None))[index]
            residual = actual-calculated if actual is not None and calculated is not None else None
            result[period] = dict(actual=decimal_text(actual), calculated=decimal_text(calculated),
                                  residual=decimal_text(residual), missing=missing)
        a, b = result['base']['residual'], result['current']['residual']
        result['change_residual'] = decimal_text(Decimal(b)-Decimal(a)) if a != '' and b != '' else ''
        result['math_status'] = ('incomplete' if a == '' or b == '' else
                                 'exact_zero_residual' if Decimal(a) == Decimal(b) == 0 else 'nonzero_residual')
    return result
