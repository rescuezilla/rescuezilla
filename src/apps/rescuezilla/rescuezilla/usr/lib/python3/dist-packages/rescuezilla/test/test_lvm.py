# ----------------------------------------------------------------------
#   Copyright (C) 2003-2021 Steven Shiau <steven _at_ clonezilla org>
#   Copyright (C) 2019-2021 Rescuezilla.com <rescuezilla@gmail.com>
# ----------------------------------------------------------------------
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------
import json
import unittest

from parser.lvm import Lvm


class LvmTest(unittest.TestCase):
    def test_logical_volume_list_parsing(self):
        # Example contents of lvm_logv.list file
        lvm_logv_list_string = """/dev/vgtest/lvtest  Linux rev 1.0 ext4 filesystem data, UUID=b9131c40-9742-416c-b019-8b11481a86ac (extents) (64bit) (large files) (huge files)"""
        logical_volume_dict = Lvm.parse_logical_volume_device_list_string(lvm_logv_list_string)
        expected = {"/dev/vgtest/lvtest": {"metadata": "Linux rev 1.0 ext4 filesystem data, UUID=b9131c40-9742-416c-b019-8b11481a86ac (extents) (64bit) (large files) (huge files)"}}
        # pp = pprint.PrettyPrinter(indent=4)
        self.assertDictEqual(expected, logical_volume_dict)

    def test_volume_group_list_parsing(self):
        # Example contents of lvm_vg_dev.list
        lvm_vg_dev_list_string = """vgtest /dev/sdb i20UTQ-OaX3-c6nB-CiBv-Gav1-hgVf-tEkO2W"""
        volume_group_dict = Lvm.parse_volume_group_device_list_string(lvm_vg_dev_list_string)
        expected = {"vgtest": {"device_node": "/dev/sdb", "uuid": "i20UTQ-OaX3-c6nB-CiBv-Gav1-hgVf-tEkO2W"}}
        self.assertDictEqual(expected, volume_group_dict)

    def test_save_logv(self):
        # sudo pvs -o pv_all,lv_all,vg_all --reportformat json
        pvs_all_json_output = """  {
      "report": [
          {
              "pv": [
                  {"lv_uuid":"LWVXkW-Ujhd-M3pB-ZgE5-uWiW-lwXU-I8mhXQ", "lv_name":"lvtest", "lv_full_name":"vgtest/lvtest", "lv_path":"/dev/vgtest/lvtest", "lv_dm_path":"/dev/mapper/vgtest-lvtest", "lv_parent":"", "lv_layout":"linear", "lv_role":"public", "lv_initial_image_sync":"", "lv_image_synced":"", "lv_merging":"", "lv_converting":"", "lv_allocation_policy":"inherit", "lv_allocation_locked":"", "lv_fixed_minor":"", "lv_skip_activation":"", "lv_when_full":"", "lv_active":"active", "lv_active_locally":"active locally", "lv_active_remotely":"", "lv_active_exclusively":"active exclusively", "lv_major":"-1", "lv_minor":"-1", "lv_read_ahead":"auto", "lv_size":"1020.00m", "lv_metadata_size":"", "seg_count":"1", "origin":"", "origin_uuid":"", "origin_size":"", "lv_ancestors":"", "lv_full_ancestors":"", "lv_descendants":"", "lv_full_descendants":"", "raid_mismatch_count":"", "raid_sync_action":"", "raid_write_behind":"", "raid_min_recovery_rate":"", "raid_max_recovery_rate":"", "move_pv":"", "move_pv_uuid":"", "convert_lv":"", "convert_lv_uuid":"", "mirror_log":"", "mirror_log_uuid":"", "data_lv":"", "data_lv_uuid":"", "metadata_lv":"", "metadata_lv_uuid":"", "pool_lv":"", "pool_lv_uuid":"", "lv_tags":"", "lv_profile":"", "lv_lockargs":"", "lv_time":"2020-08-28 07:59:08 +0000", "lv_time_removed":"", "lv_host":"ubuntu", "lv_modules":"", "lv_historical":"", "lv_kernel_major":"253", "lv_kernel_minor":"0", "lv_kernel_read_ahead":"128.00k", "lv_permissions":"writeable", "lv_suspended":"", "lv_live_table":"live table present", "lv_inactive_table":"", "lv_device_open":"", "data_percent":"", "snap_percent":"", "metadata_percent":"", "copy_percent":"", "sync_percent":"", "cache_total_blocks":"", "cache_used_blocks":"", "cache_dirty_blocks":"", "cache_read_hits":"", "cache_read_misses":"", "cache_write_hits":"", "cache_write_misses":"", "kernel_cache_settings":"", "kernel_cache_policy":"", "kernel_metadata_format":"", "lv_health_status":"", "kernel_discards":"", "lv_check_needed":"unknown", "lv_merge_failed":"unknown", "lv_snapshot_invalid":"unknown", "vdo_operating_mode":"", "vdo_compression_state":"", "vdo_index_state":"", "vdo_used_size":"", "vdo_saving_percent":"", "lv_attr":"-wi-a-----", "pv_fmt":"lvm2", "pv_uuid":"i20UTQ-OaX3-c6nB-CiBv-Gav1-hgVf-tEkO2W", "dev_size":"1.00g", "pv_name":"/dev/sdb", "pv_major":"8", "pv_minor":"16", "pv_mda_free":"508.00k", "pv_mda_size":"1020.00k", "pv_ext_vsn":"2", "pe_start":"1.00m", "pv_size":"1020.00m", "pv_free":"0 ", "pv_used":"1020.00m", "pv_attr":"a--", "pv_allocatable":"allocatable", "pv_exported":"", "pv_missing":"", "pv_pe_count":"255", "pv_pe_alloc_count":"255", "pv_tags":"", "pv_mda_count":"1", "pv_mda_used_count":"1", "pv_ba_start":"0 ", "pv_ba_size":"0 ", "pv_in_use":"used", "pv_duplicate":"", "vg_fmt":"lvm2", "vg_uuid":"jYQyeN-vqdH-gVPg-SmNR-0xYD-2mSN-v4YMiz", "vg_name":"vgtest", "vg_attr":"wz--n-", "vg_permissions":"writeable", "vg_extendable":"extendable", "vg_exported":"", "vg_partial":"", "vg_allocation_policy":"normal", "vg_clustered":"", "vg_shared":"", "vg_size":"1020.00m", "vg_free":"0 ", "vg_sysid":"", "vg_systemid":"", "vg_lock_type":"", "vg_lock_args":"", "vg_extent_size":"4.00m", "vg_extent_count":"255", "vg_free_count":"0", "max_lv":"0", "max_pv":"0", "pv_count":"1", "vg_missing_pv_count":"0", "lv_count":"1", "snap_count":"0", "vg_seqno":"2", "vg_tags":"", "vg_profile":"", "vg_mda_count":"1", "vg_mda_used_count":"1", "vg_mda_free":"508.00k", "vg_mda_size":"1020.00k", "vg_mda_copies":"unmanaged"}
              ]
          }
      ]
  }
"""
        pvs_json_output = """  {
      "report": [
          {
              "pv": [
                  {"pv_fmt":"lvm2", "pv_uuid":"i20UTQ-OaX3-c6nB-CiBv-Gav1-hgVf-tEkO2W", "dev_size":"1.00g", "pv_name":"/dev/sdb", "pv_major":"8", "pv_minor":"16", "pv_mda_free":"508.00k", "pv_mda_size":"1020.00k", "pv_ext_vsn":"2", "pe_start":"1.00m", "pv_size":"1020.00m", "pv_free":"0 ", "pv_used":"1020.00m", "pv_attr":"a--", "pv_allocatable":"allocatable", "pv_exported":"", "pv_missing":"", "pv_pe_count":"255", "pv_pe_alloc_count":"255", "pv_tags":"", "pv_mda_count":"1", "pv_mda_used_count":"1", "pv_ba_start":"0 ", "pv_ba_size":"0 ", "pv_in_use":"used", "pv_duplicate":""}
              ]
          }
      ]
  }"""
        physical_volume_state_dict = json.loads(pvs_json_output)

        # sudo lvs -o lv_all --reportformat json
        lvs_json_output = """  {
      "report": [
          {
              "lv": [
                  {"lv_uuid":"LWVXkW-Ujhd-M3pB-ZgE5-uWiW-lwXU-I8mhXQ", "lv_name":"lvtest", "lv_full_name":"vgtest/lvtest", "lv_path":"/dev/vgtest/lvtest", "lv_dm_path":"/dev/mapper/vgtest-lvtest", "lv_parent":"", "lv_layout":"linear", "lv_role":"public", "lv_initial_image_sync":"", "lv_image_synced":"", "lv_merging":"", "lv_converting":"", "lv_allocation_policy":"inherit", "lv_allocation_locked":"", "lv_fixed_minor":"", "lv_skip_activation":"", "lv_when_full":"", "lv_active":"active", "lv_active_locally":"active locally", "lv_active_remotely":"", "lv_active_exclusively":"active exclusively", "lv_major":"-1", "lv_minor":"-1", "lv_read_ahead":"auto", "lv_size":"1020.00m", "lv_metadata_size":"", "seg_count":"1", "origin":"", "origin_uuid":"", "origin_size":"", "lv_ancestors":"", "lv_full_ancestors":"", "lv_descendants":"", "lv_full_descendants":"", "raid_mismatch_count":"", "raid_sync_action":"", "raid_write_behind":"", "raid_min_recovery_rate":"", "raid_max_recovery_rate":"", "move_pv":"", "move_pv_uuid":"", "convert_lv":"", "convert_lv_uuid":"", "mirror_log":"", "mirror_log_uuid":"", "data_lv":"", "data_lv_uuid":"", "metadata_lv":"", "metadata_lv_uuid":"", "pool_lv":"", "pool_lv_uuid":"", "lv_tags":"", "lv_profile":"", "lv_lockargs":"", "lv_time":"2020-08-28 07:59:08 +0000", "lv_time_removed":"", "lv_host":"ubuntu", "lv_modules":"", "lv_historical":"", "lv_kernel_major":"253", "lv_kernel_minor":"0", "lv_kernel_read_ahead":"128.00k", "lv_permissions":"writeable", "lv_suspended":"", "lv_live_table":"live table present", "lv_inactive_table":"", "lv_device_open":"", "data_percent":"", "snap_percent":"", "metadata_percent":"", "copy_percent":"", "sync_percent":"", "cache_total_blocks":"", "cache_used_blocks":"", "cache_dirty_blocks":"", "cache_read_hits":"", "cache_read_misses":"", "cache_write_hits":"", "cache_write_misses":"", "kernel_cache_settings":"", "kernel_cache_policy":"", "kernel_metadata_format":"", "lv_health_status":"", "kernel_discards":"", "lv_check_needed":"unknown", "lv_merge_failed":"unknown", "lv_snapshot_invalid":"unknown", "vdo_operating_mode":"", "vdo_compression_state":"", "vdo_index_state":"", "vdo_used_size":"", "vdo_saving_percent":"", "lv_attr":"-wi-a-----"}
              ]
          }
      ]
  }
"""
        logical_volume_state_dict = json.loads(lvs_json_output)

        # sudo vgs -o vg_all --reportformat json
        vgs_json_output = """  {
      "report": [
          {
              "vg": [
                  {"vg_fmt":"lvm2", "vg_uuid":"jYQyeN-vqdH-gVPg-SmNR-0xYD-2mSN-v4YMiz", "vg_name":"vgtest", "vg_attr":"wz--n-", "vg_permissions":"writeable", "vg_extendable":"extendable", "vg_exported":"", "vg_partial":"", "vg_allocation_policy":"normal", "vg_clustered":"", "vg_shared":"", "vg_size":"1020.00m", "vg_free":"0 ", "vg_sysid":"", "vg_systemid":"", "vg_lock_type":"", "vg_lock_args":"", "vg_extent_size":"4.00m", "vg_extent_count":"255", "vg_free_count":"0", "max_lv":"0", "max_pv":"0", "pv_count":"1", "vg_missing_pv_count":"0", "lv_count":"1", "snap_count":"0", "vg_seqno":"2", "vg_tags":"", "vg_profile":"", "vg_mda_count":"1", "vg_mda_used_count":"1", "vg_mda_free":"508.00k", "vg_mda_size":"1020.00k", "vg_mda_copies":"unmanaged"}
              ]
          }
      ]
  }
"""
        volume_group_state_dict = json.loads(vgs_json_output)
