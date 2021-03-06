from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.utils.encoding import force_unicode


class LinksManager(models.Manager):

    def for_model(self, model):
        """
        QuerySet for all links for a particular model (either an instance or
        a class).
        """
        ct = ContentType.objects.get_for_model(model)
        qs = self.get_query_set().select_related('link_type').filter(
            active=True, content_type=ct)
        if isinstance(model, models.Model):
            qs = qs.filter(object_pk=force_unicode(model._get_pk_val()))
        return qs
