import re

TIMESPEC_RE = re.compile('^(\d+)([a-z])$')

def translate_timespec(string):
    """Parses a storm duration-ish timespec like "5m 20s" and returns the
    corresponding number of seconds.
    """
    components = string.split(' ')
    time_translator = {
        'w': 60*60*24*7,
        'd': 60*60*24,
        'h': 60*60,
        'm': 60,
        's': 1,
    }
    res = 0
    for component in components:
        if component == '':
            continue
        match = TIMESPEC_RE.match(component)
        if match is None:
            raise ValueError("Can't parse the timespec", string, 'component=', component)
        multiplier = time_translator[match.group(2)]
        number = int(match.group(1))
        res += multiplier * number
    return res


def _topology_name(topology_re, topology):
    """Returns the name if a config's topology regex matches, None otherwise."""
    match = topology_re.match(topology.get('name'))
    if match:
        return match.group(1)
    else:
        return None

def collect_topologies(topology_re, topologies):
    """
    Filter out topologies matching the regex, and collect the newest ACTIVE one.
    Returns a dictionary of the form `{taggable_name: topology}`
    """
    ret = dict()
    for topo in topologies:
        name = _topology_name(topology_re, topo)
        # Skip if the topology name doesn't match the ones we want:
        if name is None or topo.get('status', 'KILLED') != 'ACTIVE':
            continue
        if name not in ret:
            ret[name] = []
        ret[name].append(topo)
    topo_key = lambda x: translate_timespec(x['uptime'])
    return {name: sorted(value, key=topo_key)[0] for name, value in ret.iteritems()}
