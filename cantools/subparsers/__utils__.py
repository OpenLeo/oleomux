from cantools.database.can.message import Message
from cantools.database.can.signal import NamedSignalValue

MULTI_LINE_FMT = '''
{message}(
{signals}
)\
'''


def _format_signals(message, decoded_signals):
    formatted_signals = []

    for signal in message.signals:
        try:
            value = decoded_signals[signal.name]
        except KeyError:
            continue

        signal_name = signal.name

        if signal.unit is None or \
           isinstance(value, NamedSignalValue) or \
           isinstance(value, str):

            formatted_signal = f'{signal_name}: {value}'

        else:
            formatted_signal = f'{signal_name}: {value} {signal.unit}'

        formatted_signals.append(formatted_signal)

    return formatted_signals


def _format_message_single_line(message, formatted_signals):
    return ' {}({})'.format(message.name,
                            ', '.join(formatted_signals))


def _format_message_multi_line(message, formatted_signals):
    indented_signals = [
        '    ' + formatted_signal
        for formatted_signal in formatted_signals
    ]

    return MULTI_LINE_FMT.format(message=message.name,
                                 signals=',\n'.join(indented_signals))

def _format_container_single_line(message, decoded_data):
    contained_list = list()
    for cm, signals in decoded_data:
        if isinstance(cm, Message):
            formatted_cm_signals = _format_signals(cm, signals)
            formatted_cm = _format_message_single_line(cm, formatted_cm_signals)
            contained_list.append(formatted_cm)
        else:
            header_id = cm
            data = signals
            contained_list.append(
                f'(Unknown contained message: Header ID: 0x{header_id:x}, '
                f'Data: {data.hex()})')

    return f' {message.name}({", ".join(contained_list)})'


def _format_container_multi_line(message, decoded_data):
    contained_list = list()
    for cm, signals in decoded_data:
        if isinstance(cm, Message):
            formatted_cm_signals = _format_signals(cm, signals)
            formatted_cm = _format_message_multi_line(cm, formatted_cm_signals)
            formatted_cm = formatted_cm.replace('\n', '\n    ')
            contained_list.append('    '+formatted_cm.strip())
        else:
            header_id = cm
            data = signals
            contained_list.append(
                f'    Unknown contained message (Header ID: 0x{header_id:x}, '
                f'Data: {data.hex()})')

    return \
        f'\n{message.name}(\n' + \
        ',\n'.join(contained_list) + \
        '\n)'

def format_message_by_frame_id(dbase,
                               frame_id,
                               data,
                               decode_choices,
                               single_line,
                               decode_containers):
    try:
        message = dbase.get_message_by_frame_id(frame_id)
    except KeyError:
        return ' Unknown frame id {0} (0x{0:x})'.format(frame_id)

    if message.is_container:
        if decode_containers:
            return format_container_message(message,
                                            data,
                                            decode_choices,
                                            single_line)
        else:
            return f' Frame 0x{frame_id:x} is a container message'

    return format_message(message, data, decode_choices, single_line)

def format_container_message(message, data, decode_choices, single_line):
    try:
        decoded_message = message.decode(data,
                                         decode_choices,
                                         decode_containers=True)
    except Exception as e:
        return ' ' + str(e)

    if single_line:
        return _format_container_single_line(message, decoded_message)
    else:
        return _format_container_multi_line(message, decoded_message)


def format_message(message, data, decode_choices, single_line):
    try:
        decoded_signals = message.decode(data, decode_choices)
    except Exception as e:
        return ' ' + str(e)

    formatted_signals = _format_signals(message, decoded_signals)

    if single_line:
        return _format_message_single_line(message, formatted_signals)
    else:
        return _format_message_multi_line(message, formatted_signals)

def format_multiplexed_name(message, data, decode_choices):
    decoded_signals = message.decode(data, decode_choices)

    # The idea here is that we rely on the sorted order of the Signals, and
    # then simply go through each possible Multiplexer and build a composite
    # key consisting of the Message name prepended to all the possible MUX
    # Signals (and their values). This composite key is therefore unique for
    # all the different possible enumerations of MUX values, which allows us
    # to display each MUXed Message on its own separate line.
    result = [message.name]

    for signal in message.signals:
        if signal.is_multiplexer:
            if signal.name in decoded_signals:
                result.append(str(decoded_signals[signal.name]))
            elif signal.initial is not None:
                result.append(str(signal.initial))
            else:
                result.append('0')

    return '__'.join(result)
