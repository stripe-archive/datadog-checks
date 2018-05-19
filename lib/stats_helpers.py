from timeit import default_timer as timer

class Timing:
    WITH_COUNT = 1
    WITH_TIMING = 2

    def __init__(self, check, metric_name, tags={}, emit=None):
        self.check = check
        self.metric_name = metric_name
        self.extra_tags = tags
        self.emit = emit
    def __enter__(self):
        self.start = timer()
    def __exit__(self, exc_type, exc_value, traceback):
        self.end = timer()

        # tag with error presence and type
        tag_dict = {}
        if exc_type:
            tag_dict['is_error'] = 'true'
            try:
                tag_dict['error_type'] = exc_type.__name__.lower()
            except AttributeError:
                tag_dict['error_type'] = 'unknown'
        else:
            tag_dict['is_error'] = 'false'
            tag_dict['error_type'] = 'none'

        # tag with user-supplied tags, which are allowed to override error tags
        tag_dict.update(self.extra_tags)

        tags = ["%s:%s" % (k, v) for k, v in tag_dict.iteritems()]

        # emit either a call count or a full timing histogram
        if self.emit == self.WITH_TIMING:
            self.check.histogram(
                self.metric_name,
                int((self.end - self.start) * 1000),
                tags=tags
            )
        elif self.emit == self.WITH_COUNT:
            self.check.increment(
                # this is intended to match the format of *just* the count portion
                # of a histogram call. since check.histogram adds these suffixes
                # implicitly, but we're calling increment here, we need to add
                # it explicitly
                '%s.count' % self.metric_name,
                tags=tags
            )
