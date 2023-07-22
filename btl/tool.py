# -*- coding: utf-8 -*-
import uuid
from .shape import Shape

class Tool(object):
    API_VERSION = 1

    def __init__(self, label, shape, id=None, filename=None):
        self.id = id or str(uuid.uuid1())
        self.label = label
        self.filename = filename # Keep in mind: Not every tool is file-based
        self.shape = Shape(shape) if isinstance(shape, str) else shape

    def __str__(self):
        return '{} "{}" "{}"'.format(self.id, self.label, self.shape.name)

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def set_label(self, label):
        self.label = label

    def get_label(self):
        return self.label

    def serialize(self, serializer):
        return serializer.serialize_tool(self)

    def dump(self, indent=0, summarize=False):
        indent = ' '*indent
        print('{}Tool "{}" ({})'.format(
            indent,
            self.label,
            self.id
        ))

        shape = self.shape.get_label()
        shape_name = self.shape.name
        print('{}  Shape = {} ({})'.format(indent, shape, shape_name))

        self.shape.dump(indent=2, summarize=summarize)
