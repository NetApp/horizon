# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from django.core.urlresolvers import NoReverseMatch  # noqa
from django.core.urlresolvers import reverse
from django.template.defaultfilters import title  # noqa
from django.utils.translation import string_concat, ugettext_lazy  # noqa
from django.utils.translation import ugettext_lazy as _
from horizon import exceptions
from horizon import tables

from openstack_dashboard.api import manila
from openstack_dashboard.dashboards.project.shares.snapshots \
    import tables as snapshot_tables
from openstack_dashboard.usage import quotas


DELETABLE_STATES = ("available", "error")


class DeleteShare(tables.DeleteAction):
    data_type_singular = _("Share")
    data_type_plural = _("Shares")
    action_past = _("Scheduled deletion of %(data_type)s")
    policy_rules = (("share", "share:delete"),)

    def get_policy_target(self, request, datum=None):
        project_id = None
        if datum:
            project_id = getattr(datum, "os-share-tenant-attr:tenant_id", None)
        return {"project_id": project_id}

    def delete(self, request, obj_id):
        obj = self.table.get_object_by_id(obj_id)
        name = self.table.get_object_display(obj)
        try:
            manila.share_delete(request, obj_id)
        except Exception:
            msg = _('Unable to delete share "%s". One or more snapshots '
                    'depend on it.')
            exceptions.check_message(["snapshots", "dependent"], msg % name)
            raise

    def allowed(self, request, share=None):
        if share:
            return share.status in DELETABLE_STATES
        return True


class CreateShare(tables.LinkAction):
    name = "create"
    verbose_name = _("Create Share")
    url = "horizon:project:shares:create"
    classes = ("ajax-modal", "btn-create")
    policy_rules = (("share", "share:create"),)

    def allowed(self, request, share=None):
        usages = quotas.tenant_quota_usages(request)
        if usages['shares']['available'] <= 0:
            if "disabled" not in self.classes:
                self.classes = [c for c in self.classes] + ['disabled']
                self.verbose_name = string_concat(self.verbose_name, ' ',
                                                  _("(Quota exceeded)"))
        else:
            self.verbose_name = _("Create Share")
            classes = [c for c in self.classes if c != "disabled"]
            self.classes = classes
        return True


class EditShare(tables.LinkAction):
    name = "edit"
    verbose_name = _("Edit Share")
    url = "horizon:project:shares:update"
    classes = ("ajax-modal", "btn-edit")
    policy_rules = (("share", "share:update"),)

    def get_policy_target(self, request, datum=None):
        project_id = None
        if datum:
            project_id = getattr(datum, "os-share-tenant-attr:tenant_id", None)
        return {"project_id": project_id}

    def allowed(self, request, share=None):
        return share.status in ("available", "in-use")


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, share_id):
        share = manila.share_get(request, share_id)
        if not share.name:
            share.name = share_id
        return share


def get_size(share):
    return _("%sGB") % share.size


class SharesTableBase(tables.DataTable):
    STATUS_CHOICES = (
        ("in-use", True),
        ("available", True),
        ("creating", None),
        ("error", False),
    )
    name = tables.Column("name",
                         verbose_name=_("Name"),
                         link="horizon:project:shares:detail")
    description = tables.Column("description",
                                verbose_name=_("Description"),
                                truncate=40)
    size = tables.Column(get_size,
                         verbose_name=_("Size"),
                         attrs={'data-type': 'size'})
    status = tables.Column("status",
                           filters=(title,),
                           verbose_name=_("Status"),
                           status=True,
                           status_choices=STATUS_CHOICES)

    def get_object_display(self, obj):
        return obj.name


class SharesFilterAction(tables.FilterAction):

    def filter(self, table, shares, filter_string):
        """Naive case-insensitive search."""
        q = filter_string.lower()
        return [share for share in shares
                if q in share.name.lower()]


class ManageRules(tables.LinkAction):
    name = "manage_rules"
    verbose_name = _("Manage Rules")
    url = "horizon:project:shares:manage_rules"
    classes = ("btn-edit", )
    #policy_rules = (("share", "share:update"),)


class AddRule(tables.LinkAction):
    name = "rule_add"
    verbose_name = _("Add rule")
    url = 'horizon:project:shares:rule_add'
    classes = ("ajax-modal", "btn-create")
    #policy_rules = (("share", "share:create"),)

    def allowed(self, request, share=None):
        share = manila.share_get(request, self.table.kwargs['share_id'])
        return share.status in ("available", "in-use")

    def get_link_url(self):
        return reverse(self.url, args=[self.table.kwargs['share_id']])


class DeleteRule(tables.DeleteAction):
    data_type_singular = _("Rule")
    data_type_plural = _("Rules")
    action_past = _("Scheduled deletion of %(data_type)s")
    #policy_rules = (("share", "share:delete"),)

    def delete(self, request, obj_id):
        obj = self.table.get_object_by_id(obj_id)
        name = self.table.get_object_display(obj)
        try:
            manila.share_deny(request, self.table.kwargs['share_id'], obj_id)
        except Exception:
            msg = _('Unable to delete rule "%s".')
            exceptions.handle(request, msg)
#
#
#class UpdateRuleRow(UpdateRow):
#
#    def get_data(self, request, rule_id):
#        share = manila.share_rules_list(request, search_opts={'id': rule_id})
#        if not share.name:
#            share.name = share_id
#        return share


class RulesTable(tables.DataTable):
    type = tables.Column("access_type", verbose_name=_("Type"))
    access = tables.Column("access_to", verbose_name=_("Access to"))
    status = tables.Column("state", verbose_name=_("Status"))

    class Meta:
        name = "rules"
        verbose_name = _("Rules")
        status_columns = ["status"]
        #row_class = UpdateRuleRow
        table_actions = (DeleteRule, AddRule)
        row_actions = (DeleteRule, )


def get_share_network(share):
    return share.share_network_name if share.share_network_name != "None" else None


class SharesTable(SharesTableBase):
    name = tables.Column("name",
                         verbose_name=_("Name"),
                         link="horizon:project:shares:detail")
    proto = tables.Column("share_proto",
                          verbose_name=_("Protocol"))
    share_network = tables.Column("share_network",
                                  verbose_name=_("Share Network"),
                                  empty_value="-")

    class Meta:
        name = "shares"
        verbose_name = _("Shares")
        status_columns = ["status"]
        row_class = UpdateRow
        table_actions = (CreateShare, DeleteShare, SharesFilterAction)
        row_actions = (EditShare, snapshot_tables.CreateSnapshot, DeleteShare,
                       ManageRules)