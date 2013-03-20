from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from .managers import SuggestionsManager


class Suggestion(models.Model):
    """Data improvement suggestions.  Designed to implement suggestions queue
    for content editors.

    A suggestion can be either:

    * Automatically applied once approved (for that data needs to to supplied
      and action be one of: ADD, REMOVE, SET. If the the field to be
      modified is a relation manger, `content_object` should be provided as
      well.
    * Manually applied, in that case a content should be provided for
      `suggested_text`.

    The model is generic is possible, and designed for building custom
    suggestion forms for each content type.

    """

    ADD, REMOVE, SET, REPLACE, FREE_TEXT = range(5)

    SUGGEST_CHOICES = (
        (ADD, _('Add related object to m2m relation')),
        (REMOVE, _('Remove related object from m2m relation')),
        (SET, _('Set field value. For m2m _replaces_ (use ADD if needed)')),
        (FREE_TEXT, _("Free text suggestion")),
    )

    NEW, FIXED, WONTFIX = 0, 1, 2

    RESOLVE_CHOICES = (
        (NEW, _('New')),
        (FIXED, _('Fixed')),
        (WONTFIX, _("Won't Fix")),
    )

    suggested_at = models.DateTimeField(
        _('Suggested at'), blank=True, default=datetime.now, db_index=True)
    suggested_by = models.ForeignKey(User, related_name='suggestions')

    content_type = models.ForeignKey(
        ContentType, related_name='suggestion_content')
    content_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'content_id')

    suggestion_action = models.PositiveIntegerField(
        _('Suggestion type'), choices=SUGGEST_CHOICES)

    # suggestion can be either a foreign key adding to some related manager,
    # set some content text, etc
    suggested_field = models.CharField(
        max_length=255, blank=True, null=True,
        help_text=_('Field or related manager to change'))
    suggested_type = models.ForeignKey(
        ContentType, related_name='suggested_content', blank=True, null=True)
    suggested_id = models.PositiveIntegerField(blank=True, null=True)
    suggested_object = generic.GenericForeignKey('suggested_type', 'suggested_id')
    suggested_text = models.TextField(_('Free text'), blank=True, null=True)

    resolved_at = models.DateTimeField(_('Resolved at'), blank=True, null=True)
    resolved_by = models.ForeignKey(
        User, related_name='resolved_suggestions', blank=True, null=True)
    resolved_status = models.IntegerField(
        _('Resolved status'), db_index=True, default=NEW,
        choices=RESOLVE_CHOICES)

    objects = SuggestionsManager()

    class Meta:
        verbose_name = _('Suggestion')
        verbose_name_plural = _('Suggestions')

    def auto_apply(self, resolved_by):

        action_map = {
            self.SET: self.auto_apply_set,
            self.ADD: self.auto_apply_add,
            self.REMOVE: self.auto_applly_remove,
        }

        action = action_map.get(self.suggestion_action, None)

        if action is None:
            raise ValueError("{0} can't be auto applied".format(
                self.get_suggestion_action_display()
            ))

        action()

        self.resolved_by = resolved_by
        self.resolved_status = self.FIXED
        self.resolved_at = datetime.now()

        self.save()

    def auto_apply_set(self):
        "Auto updates a field"

        ct_obj = self.content_object

        field_name = self.suggested_field
        field, model, direct, m2m = ct_obj._meta.get_field_by_name(field_name)

        if m2m:
            value = [self.suggested_object]
        elif isinstance(field, models.ForeignKey):
            value = self.suggested_object
        else:
            value = self.suggested_text

        setattr(ct_obj, field_name, value)
        ct_obj.save()

    def auto_apply_add(self):
        "Auto add to m2m"

        ct_obj = self.content_object

        field_name = self.suggested_field
        field, model, direct, m2m = ct_obj._meta.get_field_by_name(field_name)

        if not m2m:
            raise ValueError("{0} can be auto applied only on m2m".format(
                self.get_suggestion_action_display()
            ))

        getattr(ct_obj, field_name).add(self.suggested_object)

    def auto_applly_remove(self):
        "Auto delete from m2m"

        ct_obj = self.content_object

        field_name = self.suggested_field
        field, model, direct, m2m = ct_obj._meta.get_field_by_name(field_name)

        if not m2m:
            raise ValueError("{0} can be auto applied only on m2m".format(
                self.get_suggestion_action_display()
            ))

        getattr(ct_obj, field_name).remove(self.suggested_object)