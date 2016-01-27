﻿#-------------------------------------------------------------------------
# Copyright (c) Microsoft.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#--------------------------------------------------------------------------
import unittest


from datetime import datetime
from dateutil.tz import tzutc
from azure.storage.table import (
    Entity,
    EntityProperty,
    TableService,
    TableBatch,
    EdmType,
    AzureBatchOperationError,
    AzureBatchValidationError,
)
from tests.common_recordingtestcase import (
    record,
)
from tests.testcase import StorageTestCase

#------------------------------------------------------------------------------

MAX_RETRY = 60
#------------------------------------------------------------------------------


class StorageTableBatchTest(StorageTestCase):

    def setUp(self):
        super(StorageTableBatchTest, self).setUp()

        self.ts = self._create_storage_service(TableService, self.settings)

        self.table_name = self.get_resource_name('uttable')

        self.additional_table_names = []

    def tearDown(self):
        if not self.is_playback():
            try:
                self.ts.delete_table(self.table_name)
            except:
                pass

            for name in self.additional_table_names:
                try:
                    self.ts.delete_table(name)
                except:
                    pass

        return super(StorageTableBatchTest, self).tearDown()

    #--Helpers-----------------------------------------------------------------
    def _create_table(self, table_name):
        '''
        Creates a table with the specified name.
        '''
        self.ts.create_table(table_name, True)

    def _create_table_with_default_entities(self, table_name, entity_count):
        '''
        Creates a table with the specified name and adds entities with the
        default set of values. PartitionKey is set to 'MyPartition' and RowKey
        is set to a unique counter value starting at 1 (as a string).
        '''
        entities = []
        self._create_table(table_name)
        for i in range(1, entity_count + 1):
            entities.append(self.ts.insert_entity(
                table_name,
                self._create_default_entity_dict('MyPartition', str(i))))
        return entities

    def _create_default_entity_dict(self, partition, row):
        '''
        Creates a dictionary-based entity with fixed values, using all
        of the supported data types.
        '''
        return {'PartitionKey': partition,
                'RowKey': row,
                'age': 39,
                'sex': 'male',
                'married': True,
                'deceased': False,
                'optional': None,
                'ratio': 3.1,
                'evenratio': 3.0,
                'large': 933311100,
                'Birthday': datetime(1973, 10, 4),
                'birthday': datetime(1970, 10, 4),
                'other': EntityProperty(EdmType.INT32, 20),
                'clsid': EntityProperty(
                    EdmType.GUID,
                    'c9da6455-213d-42c9-9a79-3e9149a57833')}

    def _create_updated_entity_dict(self, partition, row):
        '''
        Creates a dictionary-based entity with fixed values, with a
        different set of values than the default entity. It
        adds fields, changes field values, changes field types,
        and removes fields when compared to the default entity.
        '''
        return {'PartitionKey': partition,
                'RowKey': row,
                'age': 'abc',
                'sex': 'female',
                'sign': 'aquarius',
                'birthday': datetime(1991, 10, 4)}

    def _assert_default_entity(self, entity):
        '''
        Asserts that the entity passed in matches the default entity.
        '''
        self.assertEqual(entity.age, 39)
        self.assertEqual(entity.sex, 'male')
        self.assertEqual(entity.married, True)
        self.assertEqual(entity.deceased, False)
        self.assertFalse(hasattr(entity, "optional"))
        self.assertFalse(hasattr(entity, "aquarius"))
        self.assertEqual(entity.ratio, 3.1)
        self.assertEqual(entity.evenratio, 3.0)
        self.assertEqual(entity.large, 933311100)
        self.assertEqual(entity.Birthday, datetime(1973, 10, 4, tzinfo=tzutc()))
        self.assertEqual(entity.birthday, datetime(1970, 10, 4, tzinfo=tzutc()))
        self.assertIsInstance(entity.other, EntityProperty)
        self.assertEqual(entity.other.type, EdmType.INT32)
        self.assertEqual(entity.other.value, 20)
        self.assertIsInstance(entity.clsid, EntityProperty)
        self.assertEqual(entity.clsid.type, EdmType.GUID)
        self.assertEqual(entity.clsid.value,
                         'c9da6455-213d-42c9-9a79-3e9149a57833')
        self.assertTrue(hasattr(entity, "Timestamp"))
        self.assertIsInstance(entity.Timestamp, datetime)
        self.assertIsNotNone(entity.etag)

    def _assert_updated_entity(self, entity):
        '''
        Asserts that the entity passed in matches the updated entity.
        '''
        self.assertEqual(entity.age, 'abc')
        self.assertEqual(entity.sex, 'female')
        self.assertFalse(hasattr(entity, "married"))
        self.assertFalse(hasattr(entity, "deceased"))
        self.assertEqual(entity.sign, 'aquarius')
        self.assertFalse(hasattr(entity, "optional"))
        self.assertFalse(hasattr(entity, "ratio"))
        self.assertFalse(hasattr(entity, "evenratio"))
        self.assertFalse(hasattr(entity, "large"))
        self.assertFalse(hasattr(entity, "Birthday"))
        self.assertEqual(entity.birthday, datetime(1991, 10, 4, tzinfo=tzutc()))
        self.assertFalse(hasattr(entity, "other"))
        self.assertFalse(hasattr(entity, "clsid"))
        self.assertTrue(hasattr(entity, "Timestamp"))
        self.assertIsNotNone(entity.etag)

    #--Test cases for batch ---------------------------------------------

    @record
    def test_batch_insert(self):
        # Arrange
        self._create_table(self.table_name)

        # Act
        entity = Entity()
        entity.PartitionKey = '001'
        entity.RowKey = 'batch_insert'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()

        batch = TableBatch()
        batch.insert_entity(entity)
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertIsNotNone(resp)
        result = self.ts.get_entity(self.table_name, '001', 'batch_insert')
        self.assertEqual(resp[0], result.etag)

    @record
    def test_batch_update(self):
        # Arrange
        self._create_table(self.table_name)

        # Act
        entity = Entity()
        entity.PartitionKey = '001'
        entity.RowKey = 'batch_update'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()
        self.ts.insert_entity(self.table_name, entity)

        entity = self.ts.get_entity(self.table_name, '001', 'batch_update')
        self.assertEqual(3, entity.test3)
        entity.test2 = 'value1'

        batch = TableBatch()
        batch.update_entity(entity)
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertIsNotNone(resp)
        entity = self.ts.get_entity(self.table_name, '001', 'batch_update')
        self.assertEqual('value1', entity.test2)
        self.assertEqual(resp[0], entity.etag)

    @record
    def test_batch_merge(self):
        # Arrange
        self._create_table(self.table_name)

        # Act
        entity = Entity()
        entity.PartitionKey = '001'
        entity.RowKey = 'batch_merge'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()
        self.ts.insert_entity(self.table_name, entity)

        entity = self.ts.get_entity(self.table_name, '001', 'batch_merge')
        self.assertEqual(3, entity.test3)
        entity = Entity()
        entity.PartitionKey = '001'
        entity.RowKey = 'batch_merge'
        entity.test2 = 'value1'

        batch = TableBatch()
        batch.merge_entity(entity)
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertIsNotNone(resp)
        entity = self.ts.get_entity(self.table_name, '001', 'batch_merge')
        self.assertEqual('value1', entity.test2)
        self.assertEqual(1234567890, entity.test4)
        self.assertEqual(resp[0], entity.etag)

    @record
    def test_batch_update_if_match(self):
        # Arrange
        etags = self._create_table_with_default_entities(self.table_name, 1)

        # Act
        sent_entity = self._create_updated_entity_dict('MyPartition', '1')
        batch = TableBatch()
        batch.update_entity(sent_entity, if_match=etags[0])
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertIsNotNone(resp)
        received_entity = self.ts.get_entity(
            self.table_name, 'MyPartition', '1')
        self._assert_updated_entity(received_entity)
        self.assertEqual(resp[0], received_entity.etag)

    @record
    def test_batch_update_if_doesnt_match(self):
        # Arrange
        self._create_table_with_default_entities(self.table_name, 2)

        # Act
        sent_entity1 = self._create_updated_entity_dict('MyPartition', '1')
        sent_entity2 = self._create_updated_entity_dict('MyPartition', '2')

        batch = TableBatch()
        batch.update_entity(
            sent_entity1,
            if_match=u'W/"datetime\'2012-06-15T22%3A51%3A44.9662825Z\'"')
        batch.update_entity(sent_entity2)
        try:
            self.ts.commit_batch(self.table_name, batch)
        except AzureBatchOperationError as error:
            self.assertEqual(error.code, 'UpdateConditionNotSatisfied')
            self.assertTrue(str(error).startswith('0:The update condition specified in the request was not satisfied.'))
        else:
            self.fail('AzureBatchOperationError was expected')

        # Assert
        received_entity = self.ts.get_entity(
            self.table_name, 'MyPartition', '1')
        self._assert_default_entity(received_entity)
        received_entity = self.ts.get_entity(
            self.table_name, 'MyPartition', '2')
        self._assert_default_entity(received_entity)

    @record
    def test_batch_insert_replace(self):
        # Arrange
        self._create_table(self.table_name)

        # Act
        entity = Entity()
        entity.PartitionKey = '001'
        entity.RowKey = 'batch_insert_replace'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()

        batch = TableBatch()
        batch.insert_or_replace_entity(entity)
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertIsNotNone(resp)
        entity = self.ts.get_entity(
            self.table_name, '001', 'batch_insert_replace')
        self.assertIsNotNone(entity)
        self.assertEqual('value', entity.test2)
        self.assertEqual(1234567890, entity.test4)
        self.assertEqual(resp[0], entity.etag)

    @record
    def test_batch_insert_merge(self):
        # Arrange
        self._create_table(self.table_name)

        # Act
        entity = Entity()
        entity.PartitionKey = '001'
        entity.RowKey = 'batch_insert_merge'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()

        batch = TableBatch()
        batch.insert_or_merge_entity(entity)
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertIsNotNone(resp)
        entity = self.ts.get_entity(
            self.table_name, '001', 'batch_insert_merge')
        self.assertIsNotNone(entity)
        self.assertEqual('value', entity.test2)
        self.assertEqual(1234567890, entity.test4)
        self.assertEqual(resp[0], entity.etag)

    @record
    def test_batch_delete(self):
        # Arrange
        self._create_table(self.table_name)

        # Act
        entity = Entity()
        entity.PartitionKey = '001'
        entity.RowKey = 'batch_delete'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()
        self.ts.insert_entity(self.table_name, entity)

        entity = self.ts.get_entity(self.table_name, '001', 'batch_delete')
        self.assertEqual(3, entity.test3)

        batch = TableBatch()
        batch.delete_entity('001', 'batch_delete')
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertIsNotNone(resp)
        self.assertIsNone(resp[0])

    @record
    def test_batch_inserts(self):
        # Arrange
        self._create_table(self.table_name)

        # Act
        entity = Entity()
        entity.PartitionKey = 'batch_inserts'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')

        batch = TableBatch()
        for i in range(100):
            entity.RowKey = str(i)
            batch.insert_entity(entity)
        self.ts.commit_batch(self.table_name, batch)

        entities = self.ts.query_entities(
            self.table_name, "PartitionKey eq 'batch_inserts'", '')

        # Assert
        self.assertIsNotNone(entities)
        self.assertEqual(100, len(entities))

    @record
    def test_batch_all_operations_together(self):
        # Arrange
        self._create_table(self.table_name)

         # Act
        entity = Entity()
        entity.PartitionKey = '003'
        entity.RowKey = 'batch_all_operations_together-1'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()
        self.ts.insert_entity(self.table_name, entity)
        entity.RowKey = 'batch_all_operations_together-2'
        self.ts.insert_entity(self.table_name, entity)
        entity.RowKey = 'batch_all_operations_together-3'
        self.ts.insert_entity(self.table_name, entity)
        entity.RowKey = 'batch_all_operations_together-4'
        self.ts.insert_entity(self.table_name, entity)

        batch = TableBatch()
        entity.RowKey = 'batch_all_operations_together'
        batch.insert_entity(entity)
        entity.RowKey = 'batch_all_operations_together-1'
        batch.delete_entity(entity.PartitionKey, entity.RowKey)
        entity.RowKey = 'batch_all_operations_together-2'
        entity.test3 = 10
        batch.update_entity(entity)
        entity.RowKey = 'batch_all_operations_together-3'
        entity.test3 = 100
        batch.merge_entity(entity)
        entity.RowKey = 'batch_all_operations_together-4'
        entity.test3 = 10
        batch.insert_or_replace_entity(entity)
        entity.RowKey = 'batch_all_operations_together-5'
        batch.insert_or_merge_entity(entity)
        resp = self.ts.commit_batch(self.table_name, batch)

        # Assert
        self.assertEqual(6, len(resp))
        entities = self.ts.query_entities(
            self.table_name, "PartitionKey eq '003'", '')
        self.assertEqual(5, len(entities))

    @record
    def test_batch_all_operations_together_context_manager(self):
        # Arrange
        self._create_table(self.table_name)

         # Act
        entity = Entity()
        entity.PartitionKey = '003'
        entity.RowKey = 'batch_all_operations_together-1'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()
        self.ts.insert_entity(self.table_name, entity)
        entity.RowKey = 'batch_all_operations_together-2'
        self.ts.insert_entity(self.table_name, entity)
        entity.RowKey = 'batch_all_operations_together-3'
        self.ts.insert_entity(self.table_name, entity)
        entity.RowKey = 'batch_all_operations_together-4'
        self.ts.insert_entity(self.table_name, entity)

        with self.ts.batch(self.table_name) as batch:
            entity.RowKey = 'batch_all_operations_together'
            batch.insert_entity(entity)
            entity.RowKey = 'batch_all_operations_together-1'
            batch.delete_entity(entity.PartitionKey, entity.RowKey)
            entity.RowKey = 'batch_all_operations_together-2'
            entity.test3 = 10
            batch.update_entity(entity)
            entity.RowKey = 'batch_all_operations_together-3'
            entity.test3 = 100
            batch.merge_entity(entity)
            entity.RowKey = 'batch_all_operations_together-4'
            entity.test3 = 10
            batch.insert_or_replace_entity(entity)
            entity.RowKey = 'batch_all_operations_together-5'
            batch.insert_or_merge_entity(entity)

        # Assert
        entities = self.ts.query_entities(
            self.table_name, "PartitionKey eq '003'", '')
        self.assertEqual(5, len(entities))

    @record
    def test_batch_reuse(self):
        # Arrange
        self._create_table(self.table_name)

        self.additional_table_names.append('table2')
        self._create_table('table2')

         # Act
        entity = Entity()
        entity.PartitionKey = '003'
        entity.RowKey = 'batch_all_operations_together-1'
        entity.test = EntityProperty(EdmType.BOOLEAN, 'true')
        entity.test2 = 'value'
        entity.test3 = 3
        entity.test4 = EntityProperty(EdmType.INT64, '1234567890')
        entity.test5 = datetime.utcnow()

        batch = TableBatch()
        batch.insert_entity(entity)
        entity.RowKey = 'batch_all_operations_together-2'
        batch.insert_entity(entity)
        entity.RowKey = 'batch_all_operations_together-3'
        batch.insert_entity(entity)
        entity.RowKey = 'batch_all_operations_together-4'
        batch.insert_entity(entity)

        self.ts.commit_batch(self.table_name, batch)
        self.ts.commit_batch('table2', batch)

        batch = TableBatch()
        entity.RowKey = 'batch_all_operations_together'
        batch.insert_entity(entity)
        entity.RowKey = 'batch_all_operations_together-1'
        batch.delete_entity(entity.PartitionKey, entity.RowKey)
        entity.RowKey = 'batch_all_operations_together-2'
        entity.test3 = 10
        batch.update_entity(entity)
        entity.RowKey = 'batch_all_operations_together-3'
        entity.test3 = 100
        batch.merge_entity(entity)
        entity.RowKey = 'batch_all_operations_together-4'
        entity.test3 = 10
        batch.insert_or_replace_entity(entity)
        entity.RowKey = 'batch_all_operations_together-5'
        batch.insert_or_merge_entity(entity)

        self.ts.commit_batch(self.table_name, batch)
        resp = self.ts.commit_batch('table2', batch)

        # Assert
        self.assertEqual(6, len(resp))
        entities = self.ts.query_entities(
            self.table_name, "PartitionKey eq '003'", '')
        self.assertEqual(5, len(entities))

    @record
    def test_batch_same_row_operations_fail(self):
        # Arrange
        self._create_table(self.table_name)
        entity = self._create_default_entity_dict('001', 'batch_negative_1')
        self.ts.insert_entity(self.table_name, entity)

        # Act
        with self.assertRaises(AzureBatchValidationError):
            batch = TableBatch()

            entity = self._create_updated_entity_dict(
                '001', 'batch_negative_1')
            batch.update_entity(entity)

            entity = self._create_default_entity_dict(
                '001', 'batch_negative_1')
            batch.merge_entity(entity)

        # Assert

    @record
    def test_batch_different_partition_operations_fail(self):
        # Arrange
        self._create_table(self.table_name)
        entity = self._create_default_entity_dict('001', 'batch_negative_1')
        self.ts.insert_entity(self.table_name, entity)

        # Act
        with self.assertRaises(AzureBatchValidationError):
            batch = TableBatch()

            entity = self._create_updated_entity_dict(
                '001', 'batch_negative_1')
            batch.update_entity(entity)

            entity = self._create_default_entity_dict(
                '002', 'batch_negative_1')
            batch.insert_entity(entity)

        # Assert

    @record
    def test_batch_too_many_ops(self):
        # Arrange
        self._create_table(self.table_name)
        entity = self._create_default_entity_dict('001', 'batch_negative_1')
        self.ts.insert_entity(self.table_name, entity)

        # Act
        with self.assertRaises(AzureBatchValidationError):
            batch = TableBatch()
            for i in range(0, 101):
                entity = Entity()
                entity.PartitionKey = 'large'
                entity.RowKey = 'item{0}'.format(i)
                batch.insert_entity(entity)
            self.ts.commit_batch(self.table_name, batch)

        # Assert

#------------------------------------------------------------------------------
if __name__ == '__main__':
    unittest.main()