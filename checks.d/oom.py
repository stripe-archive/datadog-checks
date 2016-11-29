import os
import re

from checks import AgentCheck

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

class OOM(AgentCheck):
    def check(self, instance):
        kernlogRE = re.compile(instance.get('kernel_line_regex'))
        killedRE = re.compile(instance.get('kill_message_regex', re.IGNORECASE))

        last = None

        try:
            fh = open(instance.get('logfile'), 'rt')
        except IOError, err:
            level = AgentCheck.UNKNOWN
            if err.errno == 2:
                level = AgentCheck.WARNING
            else:
                level = AgentCheck.CRITICAL

            self.service_check('system.oom', level, message=str(err))
        else:
            killed = None
            with fh:
                for line in reverse_readline(fh):
                    result = kernlogRE.match(line)

                    if not result:
                        continue

                    results = result.groupdict()

                    message = results['message']

                    if 'uptime' in results:
                        uptime = float(results['uptime'])

                        # only process lines since the last reboot
                        if last != None and uptime > last:
                            break

                        last = uptime

                    killed = killedRE.match(message)
                    if killed:
                        break

            if killed == None:
                self.service_check('system.oom', AgentCheck.OK)
            else:
                self.service_check('system.oom', AgentCheck.CRITICAL,
                    message="Process OOM killed since last boot: %s" % killed.groupdict()
                )
