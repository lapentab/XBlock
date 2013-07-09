"""Test the workbench views."""

import json

from django.test.client import Client
from django.test import TestCase

from mock import patch
# Nose redefines assert_raises
# pylint: disable=E0611
from nose.tools import assert_raises
# pylint: enable=E0611

from xblock.core import XBlock, String, Scope
from xblock.fragment import Fragment


class TestMultipleViews(TestCase):
    """Test that we can request multiple views from an XBlock."""

    class MultiViewXBlock(XBlock):
        """A bare-bone XBlock with two views."""
        def student_view(self, _context):
            """A view, with the default name."""
            return Fragment(u"This is student view!")

        def another_view(self, _context):
            """A secondary view for this block."""
            return Fragment(u"This is another view!")

    @patch('xblock.core.XBlock.load_class', return_value=MultiViewXBlock)
    def test_multiple_views(self, _mock_load_classes):
        client = Client()

        # The default view is student_view
        response = client.get("/view/multiview/")
        self.assertIn("This is student view!", response.content)

        # We can ask for student_view directly
        response = client.get("/view/multiview/student_view/")
        self.assertIn("This is student view!", response.content)

        # We can also ask for another view.
        response = client.get("/view/multiview/another_view/")
        self.assertIn("This is another view!", response.content)


class XBlockWithHandlerAndStudentState(XBlock):
    """A bare-bone XBlock with one view and one json handler."""
    the_data = String(default="def", scope=Scope.user_state)

    def student_view(self, _context):
        """Provide the default view."""
        body = u"The data: %r." % self.the_data
        body += u":::%s:::" % self.runtime.handler_url("update_the_data")
        return Fragment(body)

    @XBlock.json_handler
    def update_the_data(self, _data):
        """Mock handler that updates the student state."""
        self.the_data = self.the_data + "x"
        return {'the_data': self.the_data}


@patch(
    'xblock.core.XBlock.load_class',
    return_value=XBlockWithHandlerAndStudentState
)
def test_xblock_with_handler(_mock_load_class):
    # Tests an XBlock that provides a handler, and has some simple
    # student state
    client = Client()

    # Initially, the data is the default.
    response = client.get("/view/xblockwithhandlerandstudentstate/")
    assert "The data: 'def'." in response.content
    parsed = response.content.split(':::')
    assert len(parsed) == 3
    handler_url = parsed[1]

    # Now change the data.
    response = client.post(handler_url, "{}", "text/json")
    the_data = json.loads(response.content)['the_data']
    assert the_data == "defx"

    # Change it again.
    response = client.post(handler_url, "{}", "text/json")
    the_data = json.loads(response.content)['the_data']
    assert the_data == "defxx"


@patch('xblock.core.XBlock.load_class', return_value=XBlock)
def test_xblock_without_handler(_mock_load_class):
    # Test that an XBlock without a handler raises an Exception
    # when we try to hit a handler on it
    client = Client()
    handler_url = "/handler/usage_175/update_the_data/?student=student_1"

    # The default XBlock implementation doesn't provide
    # a handler, so this call should raise an exception
    # (from xblock.runtime.Runtime.handle)
    with assert_raises(Exception):
        client.post(handler_url, '{}', 'text/json')


class XBlockWithoutStudentView(XBlock):
    """
    Test WorkbechRuntime.render caught `NoSuchViewError` exception path
    """
    the_data = String(default="def", scope=Scope.user_state)


@patch('xblock.core.XBlock.load_class', return_value=XBlockWithoutStudentView)
def test_xblock_no_student_view(_mock_load_class):
    # Try to get a response. Will try to render via WorkbenchRuntime.render;
    # since no view is provided in the XBlock, will return a Fragment that
    # indicates there is no view available.
    client = Client()
    response = client.get("/view/xblockwithoutstudentview/")
    assert 'No such view' in response.content
