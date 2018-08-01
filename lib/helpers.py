import os

from datetime import datetime

def reverse_readline(fh, buf_size=8192):
    """a generator that returns the lines of a file in reverse order"""
    segment = None
    offset = 0
    fh.seek(0, os.SEEK_END)
    file_size = remaining_size = fh.tell()
    while remaining_size > 0:
        offset = min(file_size, offset + buf_size)
        fh.seek(file_size - offset)
        buffer = fh.read(min(remaining_size, buf_size))
        remaining_size -= buf_size
        lines = buffer.split('\n')
        # the first line of the buffer is probably not a complete line so
        # we'll save it and append it to the last line of the next buffer
        # we read
        if segment is not None:
            # if the previous chunk starts right from the beginning of line
            # do not concact the segment to the last line of new chunk
            # instead, yield the segment first
            if buffer[-1] is not '\n':
                lines[-1] += segment
            else:
                yield segment
        segment = lines[0]
        for index in range(len(lines) - 1, 0, -1):
            if len(lines[index]):
                yield lines[index]
    # Don't yield None if the file was empty
    if segment is not None:
        yield segment


def parse_fix_timestamp(timestamp, timestamp_format, now):
    dt = datetime.strptime(timestamp, timestamp_format)
    # in the 'classic' syslog format, no year is specified. as a result,
    # we substitute in the year from the current time. On boundaries, such
    # as a timestamp on Dec 31 2018 being parsed on Jan 1 2019, the parsed
    # timestamp would become Dec 31 2019. To deal with this, we calculate
    # both a datetime "parsed as the current year" one "parsed as the prior
    # year", and return the one that's closest to the current timestamp.
    # this ensures that if we're parsing a syslog line that, say, came
    # from another server with a clock slightly ahead of ours, we don't
    # jump back a year incorrectly; instead, we interpret it as a timestamp
    # in the future.
    if dt.year == 1900:
        this_year = dt.replace(year=now.year)
        last_year = dt.replace(year=now.year-1)

        if abs(now - this_year) < abs(now - last_year):
            dt = this_year
        else:
            dt = last_year

    return dt
