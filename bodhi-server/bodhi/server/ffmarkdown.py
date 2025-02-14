# Copyright © 2014-2020 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
"""
Fedora-flavored Markdown.

Author: Ralph Bean <rbean@redhat.com>
"""

from re import escape
import typing
import xml.etree.ElementTree as etree

from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor
from markdown.inlinepatterns import InlineProcessor
import markdown.util
import pyramid.threadlocal

from bodhi.server import MENTION_RE
from bodhi.server.config import config

if typing.TYPE_CHECKING:  # pragma: no cover
    import re  # noqa: 401
    import xml  # noqa: 401


BUGZILLA_RE = r'([a-zA-Z]+)(#[0-9]{5,})'
UPDATE_RE = (r'(?:(?<!\S)|('
             + escape(config['base_address'])
             + r'updates/))([A-Z\-]+-\d{4}-[^\W_]{10})(?:(?=[\.,;:])|(?!\S))')


def user_url(name: str) -> str:
    """
    Return a URL to the given username.

    Args:
        name: The username of the user we want a URL for.
    Returns:
        A URL to the requested user.
    """
    request = pyramid.threadlocal.get_current_request()
    return request.route_url('user', name=name)


def bug_url(tracker: str, idx: typing.Union[int, str]) -> typing.Optional[str]:
    """
    Return the URL for the given bug.

    Args:
        tracker: Which bug tracker is being referenced. May be any of 'fedora',
            'gcc', 'gnome', 'kde', 'mozilla', 'pear', 'perl', 'php', 'python', 'rh', 'rhbz', or
            'sourceware'.
        idx: The bug number.
    Returns:
        The URL of the given bug or None if tracker unsupported.
    """
    try:
        trackers = {
            'fedora': "https://bugzilla.redhat.com/show_bug.cgi?id=%s",
            'gcc': "https://gcc.gnu.org/bugzilla/show_bug.cgi?id=%s",
            'gnome': "https://bugzilla.gnome.org/show_bug.cgi?id=%s",
            'kde': "https://bugs.kde.org/show_bug.cgi?id=%s",
            'mozilla': "https://bugzilla.mozilla.org/show_bug.cgi?id=%s",
            'pear': "https://pear.php.net/bugs/bug.php?id=%s",
            'perl': "https://rt.cpan.org/Public/Bug/Display.html?id=%s",
            'php': "https://bugs.php.net/bug.php?id=%s",
            'python': "https://bugs.python.org/issue%s",
            'rh': "https://bugzilla.redhat.com/show_bug.cgi?id=%s",
            'rhbz': "https://bugzilla.redhat.com/show_bug.cgi?id=%s",
            'sourceware': "https://sourceware.org/bugzilla/show_bug.cgi?id=%s"}

        return trackers[tracker.lower()] % idx

    except KeyError:
        return None


def update_url(alias: str) -> str:
    """
    Return a URL to the given update.

    Args:
        alias: The alias of the update.
    Returns:
        A URL to the requested update.
    """
    request = pyramid.threadlocal.get_current_request()
    return request.route_url('update', id=alias)


class MentionProcessor(InlineProcessor):
    """Match username mentions and point to their profiles."""

    def handleMatch(self, m: 're.Match',
                    data: str) -> typing.Tuple['xml.etree.ElementTree.Element', int, int]:
        """
        Build and return an Element that links to the matched User's profile.

        Args:
            m: The regex match on the update.
            data: The block of text around the pattern.
        Returns:
            A tuple composed by the element being added to the tree, start and end indexes
            in data that were “consumed” by the pattern.
        """
        el = etree.Element("a")
        name = markdown.util.AtomicString(m.group(1))
        el.set('href', user_url(name[1:]))
        el.text = name
        return el, m.start(0), m.end(0)


class BugzillaProcessor(InlineProcessor):
    """Match bug tracker patterns."""

    def handleMatch(self, m: 're.Match',
                    data: str) -> typing.Tuple['xml.etree.ElementTree.Element', int, int]:
        """
        Build and return an Element that links to the referenced bug.

        Args:
            m: The regex match on the update.
            data: The block of text around the pattern.
        Returns:
            A tuple composed by the element being added to the tree, start and end indexes
            in data that were “consumed” by the pattern.
        """
        tracker = markdown.util.AtomicString(m.group(1))
        idx = markdown.util.AtomicString(m.group(2))
        url = bug_url(tracker, idx[1:])

        if url is None:
            return f'{tracker}{idx}', m.start(0), m.end(0)

        el = etree.Element("a")
        el.set('href', url)
        el.text = idx
        return el, m.start(0), m.end(0)


class UpdateProcessor(InlineProcessor):
    """Match update alias pattern and link to the update."""

    def handleMatch(self, m: 're.Match',
                    data: str) -> typing.Tuple['xml.etree.ElementTree.Element', int, int]:
        """
        Build and return an Element that links to the referenced update.

        Args:
            m: The regex match on the update.
            data: The block of text around the pattern.
        Returns:
            A tuple composed by the element being added to the tree, start and end indexes
            in data that were “consumed” by the pattern.
        """
        alias = markdown.util.AtomicString(m.group(2))
        url = update_url(alias)

        el = etree.Element("a")
        el.set('href', url)
        el.text = alias
        return el, m.start(0), m.end(0)


class SurroundPostprocessor(Postprocessor):
    """A postprocessor to surround the text with a markdown <div>."""

    def run(self, text: str) -> str:
        """
        Return text wrapped in a <div> with a markdown class.

        Args:
            text: The text to wrap in a <div>.
        Returns:
            The text wrapped in a <div>.
        """
        return "<div class='markdown'>" + text + "</div>"


class BodhiExtension(Extension):
    """Bodhi's markdown Extension."""

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        """
        Extend markdown to add our patterns and postprocessor.

        Args:
            md: An instance of the Markdown class.
        """
        md.inlinePatterns.register(MentionProcessor(MENTION_RE, md), 'mention', 175)
        md.inlinePatterns.register(BugzillaProcessor(BUGZILLA_RE, md), 'bugzilla', 175)
        md.inlinePatterns.register(UpdateProcessor(UPDATE_RE, md), 'update', 175)
        md.postprocessors.register(SurroundPostprocessor(md), 'surround', 175)
