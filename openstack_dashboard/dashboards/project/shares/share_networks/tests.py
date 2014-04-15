# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
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

import django
from django.conf import settings
from django.core.urlresolvers import reverse
from django.forms import widgets
from django import http
from manilaclient import exceptions as manila_client_exc
import mock

from mox import IsA  # noqa
from neutronclient.client import exceptions

from openstack_dashboard import api
from openstack_dashboard.api import manila
from openstack_dashboard.dashboards.project.shares import test_data
from openstack_dashboard.dashboards.project.shares \
    .share_networks import tables
from openstack_dashboard.test import helpers as test
from openstack_dashboard.usage import quotas


SHARE_INDEX_URL = reverse('horizon:project:shares:index')


class ShareNetworksViewTests(test.TestCase):

    def test_create_share_network(self):
        neutron_net_id = self.networks.first().id
        formData = {'name': u'new_share_network',
                    'description': u'This is test share network',
                    'method': u'CreateForm',
                    'neutron_net_id': neutron_net_id
                    }
        for net in self.networks.list():
            formData['subnet-choices-%s' % net.id] = net.subnets[0].id
        api.manila.share_network_create = mock.Mock()
        api.neutron.network_list = mock.Mock(return_value=self.networks.list())
        api.neutron.subnet_list = mock.Mock(return_value=self.subnets.list())
        api.manila.share_network_create = mock.Mock()
        url = reverse('horizon:project:shares:create_share_network')
        res = self.client.post(url, formData)
        api.manila.share_network_create.assert_called_with(
            mock.ANY, name=formData['name'], neutron_net_id=neutron_net_id,
            neutron_subnet_id=formData['subnet-choices-%s' % neutron_net_id],
            description=formData['description'])

    def test_delete_share_network(self):
        share_network = test_data.inactive_share_network

        formData = {'action':
                    'share_networks__delete__%s' % share_network.id}

        api.manila.share_network_delete = mock.Mock()
        api.manila.share_network_get = mock.Mock(
            return_value=[test_data.inactive_share_network])
        api.manila.share_network_list = mock.Mock(
            return_value=[test_data.active_share_network,
                          test_data.inactive_share_network])
        url = reverse('horizon:project:shares:index')
        res = self.client.post(url, formData)
        api.manila.share_network_delete.assert_called_with(
            mock.ANY, test_data.inactive_share_network.id)

        self.assertRedirectsNoFollow(res, SHARE_INDEX_URL)

    def test_detail_view(self):
        share_net = test_data.active_share_network
        sec_service = test_data.sec_service
        api.manila.share_network_get = mock.Mock(return_value=share_net)
        api.manila.share_network_security_service_list = mock.Mock(
            return_value=[sec_service])
        network = self.networks.first()
        subnet = self.subnets.first()
        api.neutron.network_get = mock.Mock(return_value=network)
        api.neutron.subnet_get = mock.Mock(return_value=subnet)

        url = reverse('horizon:project:shares:share_network_detail',
                      args=[share_net.id])
        res = self.client.get(url)
        self.assertContains(res, "<h2>Share Network Details: %s</h2>"
                                 % share_net.name,
                            1, 200)
        self.assertContains(res, "<dd>%s</dd>" % share_net.name, 1, 200)
        self.assertContains(res, "<dd>%s</dd>" % share_net.id, 1, 200)
        self.assertContains(res, "<dd>%s</dd>" % network.name_or_id, 1, 200)
        self.assertContains(res, "<dd>%s</dd>" % subnet.name_or_id, 1, 200)
        self.assertContains(res, "<a href=\"/project/shares/security_service"
                                 "/%s\">%s</a>" % (sec_service.id,
                                                   sec_service.name), 1, 200)

        self.assertNoMessages()

    #def test_detail_view_network_not_found(self):
    #    share_net = test_data.active_share_network
    #    sec_service = test_data.sec_service
    #    api.manila.share_network_get = mock.Mock(return_value=share_net)
    #    api.manila.share_network_security_service_list = mock.Mock(
    #        return_value=[sec_service])
    #
    #    def raise_neutron_exc(*args, **kwargs):
    #        import pdb;pdb.set_trace()
    #        raise exceptions.NeutronClientException('fake', 500)
    #    api.neutron.network_get = mock.Mock(
    #        side_effect=raise_neutron_exc)
    #    api.neutron.subnet_get = mock.Mock(
    #        side_effect=raise_neutron_exc)
    #
    #    url = reverse('horizon:project:shares:share_network_detail',
    #                  args=[share_net.id])
    #    res = self.client.get(url)
    #    self.assertContains(res, "<h2>Share Network Details: %s</h2>"
    #                             % share_net.name,
    #                        1, 200)
    #    self.assertContains(res, "<dd>%s</dd>" % share_net.name, 1, 200)
    #    self.assertContains(res, "<dd>%s</dd>" % share_net.id, 1, 200)
    #    self.assertContains(res, "<dd>%s</dd>" % share_net.neutron_net_id,
    #                        1, 200)
    #    self.assertContains(res, "<dd>%s</dd>" % share_net.neutron_subnet_id,
    #                        1, 200)
    #    self.assertContains(res, "<a href=\"/project/shares/security_service"
    #                             "/%s\">%s</a>" % (sec_service.id,
    #                                               sec_service.name), 1, 200)
    #
    #    self.assertNoMessages()

    def test_update_share_network(self):
        share_net = test_data.inactive_share_network

        api.manila.share_network_get = mock.Mock(return_value=share_net)
        api.manila.share_network_update = mock.Mock()
        api.manila.share_network_security_service_remove = mock.Mock()
        api.manila.security_service_list = mock.Mock(
            return_value=[test_data.sec_service])

        formData = {'method': 'UpdateForm',
                    'name': share_net.name,
                    'description': share_net.description}

        url = reverse('horizon:project:shares:update_share_network',
                      args=[share_net.id])
        res = self.client.post(url, formData)
        self.assertRedirectsNoFollow(res, SHARE_INDEX_URL)
