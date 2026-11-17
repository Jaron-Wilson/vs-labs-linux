-- schema copied from a real Visual Studio 18 Browse.VC.db
-- user_version=0 page_size=8192
CREATE TABLE properties ( name text NOT NULL CONSTRAINT pk_properties_name PRIMARY KEY, value text NOT NULL);
CREATE TABLE parsers ( parser_guid text NOT NULL CONSTRAINT pk_parsers_parser_guid PRIMARY KEY, name text NOT NULL, short_name text NOT NULL);
CREATE TABLE code_item_kinds ( id integer NOT NULL CONSTRAINT pk_code_item_kinds_id PRIMARY KEY, name text NOT NULL, parser_guid text NOT NULL CONSTRAINT fk_code_item_kinds_parser_guid REFERENCES parsers(parser_guid));
CREATE TABLE projects ( id integer NOT NULL CONSTRAINT pk_projects_id PRIMARY KEY, name text NOT NULL, directory text NOT NULL, guid text NOT NULL, shared tinyint NOT NULL);
CREATE TABLE configs ( id integer NOT NULL CONSTRAINT pk_configs_id PRIMARY KEY, hash bigint NOT NULL, project_id bigint NOT NULL CONSTRAINT fk_configs_project_id REFERENCES projects(id), name text NOT NULL, attributes tinyint NOT NULL, test_frameworks integer NOT NULL, toolset_isense_identifier text, exclude_path bigint, source_path bigint, config_include_path bigint, config_framework_include_path bigint, config_options bigint, platform_include_path bigint, platform_framework_include_path bigint, platform_options bigint, options_for_reference bigint, include_path_for_reference bigint);
CREATE TABLE project_refs ( config_id bigint NOT NULL CONSTRAINT fk_project_refs_config_id REFERENCES configs(id) ON DELETE CASCADE, project_ref_guid bigint NOT NULL, project_ref_name bigint, resolved_name bigint);
CREATE TABLE files ( id integer NOT NULL CONSTRAINT pk_files_id PRIMARY KEY, timestamp bigint NOT NULL, parsetime real NOT NULL, addtime real NOT NULL, difftime real NOT NULL, name text NOT NULL, leaf_name text NOT NULL, extension text, attributes integer NOT NULL, parser_guid text NOT NULL CONSTRAINT fk_files_parser_guid REFERENCES parsers(parser_guid));
CREATE TABLE config_files ( config_id bigint NOT NULL, file_id bigint NOT NULL, attributes smallint NOT NULL, parse_timestamp bigint NOT NULL, include_path bigint, framework_include_path bigint, options bigint, CONSTRAINT pk_config_files_config_id_file_id PRIMARY KEY (config_id, file_id)) WITHOUT ROWID;
CREATE TABLE code_items ( id integer NOT NULL CONSTRAINT pk_code_items_id PRIMARY KEY, file_id bigint NOT NULL, parent_id bigint NOT NULL, kind integer NOT NULL, attributes integer NOT NULL, name text NOT NULL, type text, start_column integer NOT NULL, start_line integer NOT NULL, end_column integer NOT NULL, end_line integer NOT NULL, name_start_column integer NOT NULL, name_start_line integer NOT NULL, name_end_column integer NOT NULL, name_end_line integer NOT NULL, param_default_value text, param_default_value_start_column integer, param_default_value_start_line integer, param_default_value_end_column integer, param_default_value_end_line integer, param_number smallint, lower_name_hint text NOT NULL);
CREATE TABLE assoc_text ( code_item_id bigint NOT NULL CONSTRAINT fk_assoc_text_code_item_id REFERENCES code_items(id) ON DELETE CASCADE, kind tinyint NOT NULL, text text NOT NULL, CONSTRAINT pk_assoc_text_code_item_id_kind PRIMARY KEY (code_item_id, kind)) WITHOUT ROWID;
CREATE TABLE assoc_spans ( code_item_id bigint NOT NULL CONSTRAINT fk_assoc_spans_code_item_id REFERENCES code_items(id) ON DELETE CASCADE, kind tinyint NOT NULL, start_column integer NOT NULL, start_line integer NOT NULL, end_column integer NOT NULL, end_line integer NOT NULL, CONSTRAINT pk_assoc_spans_code_item_id_kind PRIMARY KEY (code_item_id, kind)) WITHOUT ROWID;
CREATE TABLE file_map ( code_item_id bigint NOT NULL, config_id bigint NOT NULL, file_id bigint NOT NULL);
CREATE TABLE base_class_parents ( base_code_item_id bigint NOT NULL CONSTRAINT fk_base_class_parents_base_code_item_id REFERENCES code_items(id), parent_code_item_id bigint NOT NULL CONSTRAINT fk_base_class_parents_parent_code_item_id REFERENCES code_items(id), CONSTRAINT pk_base_class_parents_base_code_item_id_parent_code_item_id PRIMARY KEY (base_code_item_id, parent_code_item_id)) WITHOUT ROWID;
CREATE TABLE shared_data ( id integer NOT NULL CONSTRAINT pk_shared_data_id PRIMARY KEY, hash integer NOT NULL, value any NOT NULL) STRICT;
CREATE TABLE hint_files ( id integer NOT NULL CONSTRAINT pk_hint_files_id PRIMARY KEY, timestamp bigint NOT NULL, name text NOT NULL);
CREATE TABLE symbols ( id integer NOT NULL CONSTRAINT pk_symbols_id PRIMARY KEY, moniker_hash bigint NOT NULL, name text NOT NULL, declaration text, kind integer NOT NULL, semantic_token_kind integer NOT NULL, symbol_kind integer NOT NULL, flags integer NOT NULL);
CREATE TABLE symbol_refs ( symbol_id bigint NOT NULL, file_id bigint NOT NULL, config_id bigint NOT NULL, decl_defn_refs bigint, usage_refs bigint, CONSTRAINT pk_symbol_refs_file_id_config_id_symbol_id PRIMARY KEY (file_id, config_id, symbol_id)) WITHOUT ROWID;
CREATE TABLE symbol_relations ( source_symbol_id bigint NOT NULL, target_symbol_id bigint NOT NULL, config_id bigint NOT NULL, kind tinyint NOT NULL, CONSTRAINT pk_symbol_relations_source_symbol_id_target_symbol_id_config_id_kind PRIMARY KEY (source_symbol_id, target_symbol_id, config_id, kind)) WITHOUT ROWID;
CREATE TABLE file_tu_map ( file_id bigint NOT NULL, tu_file_id bigint NOT NULL, config_id bigint NOT NULL);
CREATE TABLE template_args ( symbol_id bigint NOT NULL, config_id bigint NOT NULL, file_id bigint NOT NULL, offset integer NOT NULL, args bigint NOT NULL, CONSTRAINT pk_template_args_symbol_id_config_id_file_id_offset PRIMARY KEY (symbol_id, config_id, file_id, offset)) WITHOUT ROWID;
CREATE TABLE symbol_definition_ranges ( symbol_id bigint NOT NULL, config_id bigint NOT NULL, file_id bigint NOT NULL, offset integer NOT NULL, length integer NOT NULL, CONSTRAINT pk_symbol_definition_ranges_symbol_id_config_id_file_id PRIMARY KEY (symbol_id, config_id, file_id)) WITHOUT ROWID;
CREATE UNIQUE INDEX uq_files_name ON files(name);
CREATE INDEX ix_code_items_file_id ON code_items(file_id);
CREATE UNIQUE INDEX uq_file_map_code_item_id_config_id ON file_map (code_item_id,config_id);
CREATE UNIQUE INDEX uq_hint_files_name ON hint_files(name);
CREATE VIRTUAL TABLE code_items_fts USING fts5(names, content='', contentless_delete=1, tokenize="trigram");
CREATE VIRTUAL TABLE identifiers_fts USING fts5(identifiers, content='', contentless_delete=1, tokenize="unicode61 remove_diacritics 0                      categories 'C* L* M* N* P* S* Z*'                      separators ''");
CREATE VIEW configs_ex AS
         SELECT c.id, c.hash, c.project_id, c.name,
           c.attributes, c.test_frameworks, c.toolset_isense_identifier,
           exclude_path.value AS exclude_path,
           source_path.value AS source_path,
           config_include_path.value AS config_include_path,
           config_framework_include_path.value AS
             config_framework_include_path,
           config_options.value AS config_options,
           platform_include_path.value AS platform_include_path,
           platform_framework_include_path.value AS
             platform_framework_include_path,
           platform_options.value AS platform_options,
           options_for_reference.value AS options_for_reference,
           include_path_for_reference.value AS include_path_for_reference
         FROM configs AS c
         LEFT JOIN shared_data AS exclude_path ON
           c.exclude_path = exclude_path.id
         LEFT JOIN shared_data AS source_path ON c.source_path = source_path.id
         LEFT JOIN shared_data AS config_include_path ON
           c.config_include_path = config_include_path.id
         LEFT JOIN shared_data AS config_framework_include_path ON
           c.config_framework_include_path = config_framework_include_path.id
         LEFT JOIN shared_data AS config_options ON
           c.config_options = config_options.id
         LEFT JOIN shared_data AS platform_include_path ON
           c.platform_include_path = platform_include_path.id
         LEFT JOIN shared_data AS platform_framework_include_path ON
           c.platform_framework_include_path =
             platform_framework_include_path.id
         LEFT JOIN shared_data AS platform_options ON
           c.platform_options = platform_options.id
         LEFT JOIN shared_data AS options_for_reference ON
           c.options_for_reference = options_for_reference.id
         LEFT JOIN shared_data AS include_path_for_reference ON
           c.include_path_for_reference = include_path_for_reference.id;
CREATE VIEW configs_debug AS
         SELECT c.id, c.hash, c.project_id,
           replace(p.name, rtrim(p.name, replace(p.name, '\', '')), '') AS
             project_name,
           c.name, iif(c.attributes != 0, concat_ws('|', iif(c.attributes & 1 != 0, 'is_native', null), iif(c.attributes & 2 != 0, 'has_modules', null), iif(c.attributes & 4 != 0, 'symbol_indexing_completed', null), iif(c.attributes & 8 != 0, 'symbol_indexing_invalidated', null)), 'none') AS attributes,
           c.test_frameworks, c.toolset_isense_identifier, c.exclude_path,
           c.source_path, c.config_include_path,
           c.config_framework_include_path, c.config_options,
           c.platform_include_path, c.platform_framework_include_path,
           c.platform_options, c.options_for_reference,
           c.include_path_for_reference
         FROM configs_ex AS c
         INNER JOIN projects AS p ON c.project_id = p.id;
CREATE VIEW project_refs_ex AS SELECT pr.config_id, project_ref_guid.value AS project_ref_guid,       project_ref_name.value AS project_ref_name,       resolved_name.value AS resolved_name,       pr.project_ref_guid AS project_ref_guid_id FROM project_refs AS pr  LEFT JOIN shared_data AS project_ref_guid ON    pr.project_ref_guid = project_ref_guid.id  LEFT JOIN shared_data AS project_ref_name ON    pr.project_ref_name = project_ref_name.id  LEFT JOIN shared_data AS resolved_name ON    pr.resolved_name = resolved_name.id;
CREATE VIEW files_debug AS
         SELECT id, iif(timestamp != 0,
                        strftime('%m-%e-%Y %I:%M:%S %p', timestamp,
                                 'auto', 'localtime'),
                    'none') AS timestamp,
         iif(parsetime != 0,
             strftime('%M:%fs', parsetime, 'unixepoch', 'subsec'),
             'none') AS parsetime,
         iif(addtime != 0,
             strftime('%M:%fs', addtime, 'unixepoch', 'subsec'),
             'none') AS addtime,
         iif(difftime != 0,
             strftime('%M:%fs', difftime, 'unixepoch', 'subsec'),
             'none') AS difftime,
         name, leaf_name, extension, iif(attributes != 0, concat_ws('|', iif(attributes & 1 != 0, 'reparse', null), iif(attributes & 2 != 0, 'managed', null), iif(attributes & 4 != 0, 'assembly', null), iif(attributes & 8 != 0, 'nonexistent', null), iif(attributes & 16 != 0, 'module_interface', null), iif(attributes & 32 != 0, 'generalized', null), iif(attributes & 64 != 0, 'nonparsed', null), iif(attributes & 128 != 0, 'generated', null)), 'none') AS attributes, parser_guid FROM files;
CREATE VIEW config_files_ex AS
         SELECT cf.config_id, cf.file_id, cf.attributes, cf.parse_timestamp,
                include_path.value AS include_path,
                framework_include_path.value AS framework_include_path,
                options.value AS options 
         FROM config_files AS cf
         LEFT JOIN shared_data AS include_path ON
           cf.include_path = include_path.id
         LEFT JOIN shared_data AS framework_include_path ON
           cf.framework_include_path = framework_include_path.id
         LEFT JOIN shared_data AS options ON
           cf.options = options.id;
CREATE VIEW config_files_debug AS
         SELECT cf.config_id,
           concat(replace(p.name, rtrim(p.name, replace(p.name, '\', '')), ''),
                  ' - ', c.name) AS config_project_name,
           cf.file_id, f.leaf_name AS file_leaf_name, iif(cf.attributes != 0, concat_ws('|', iif(cf.attributes & 1 != 0, 'implicit', null), iif(cf.attributes & 2 != 0, 'reference', null), iif(cf.attributes & 4 != 0, 'compiled', null), iif(cf.attributes & 8 != 0, 'compiled_module', null), iif(cf.attributes & 16 != 0, 'compiled_header_unit', null), iif(cf.attributes & 32 != 0, 'compiled_pch', null), iif(cf.attributes & 64 != 0, 'explicit', null), iif(cf.attributes & 128 != 0, 'shared', null), iif(cf.attributes & 256 != 0, 'generated', null), iif(cf.attributes & 512 != 0, 'library_module', null), iif(cf.attributes & 1024 != 0, 'parse_failure', null), iif(cf.attributes & 2048 != 0, 'parse_failure_invalidated', null), iif(cf.attributes & 4096 != 0, 'parse_pending_results', null)), 'none') AS attributes,
           iif(cf.parse_timestamp != 0,
               strftime('%m-%e-%Y %I:%M:%S %p', cf.parse_timestamp, 'auto',
                        'localtime'), 'none') AS parse_timestamp,
           include_path.value AS include_path,
           framework_include_path.value AS framework_include_path,
           options.value AS options
         FROM config_files AS cf
         LEFT JOIN shared_data AS include_path ON
           cf.include_path = include_path.id
         LEFT JOIN shared_data AS framework_include_path ON
           cf.framework_include_path = framework_include_path.id
         LEFT JOIN shared_data AS options ON cf.options = options.id
         INNER JOIN files AS f ON cf.file_id = f.id
         INNER JOIN configs AS c ON cf.config_id = c.id
         INNER JOIN projects AS p ON c.project_id = p.id;
CREATE VIEW symbols_debug AS
         SELECT id, moniker_hash, name, declaration, kind, flags, CASE WHEN symbol_kind = -1 THEN 'sk_none'
WHEN symbol_kind = 0 THEN 'sk_keyword'
WHEN symbol_kind = 1 THEN 'sk_macro'
WHEN symbol_kind = 2 THEN 'sk_constant'
WHEN symbol_kind = 3 THEN 'sk_type'
WHEN symbol_kind = 4 THEN 'sk_class_or_struct_tag'
WHEN symbol_kind = 5 THEN 'sk_union_tag'
WHEN symbol_kind = 6 THEN 'sk_enum_tag'
WHEN symbol_kind = 7 THEN 'sk_variable'
WHEN symbol_kind = 8 THEN 'sk_field'
WHEN symbol_kind = 9 THEN 'sk_static_data_member'
WHEN symbol_kind = 10 THEN 'sk_member_function'
WHEN symbol_kind = 11 THEN 'sk_function'
WHEN symbol_kind = 12 THEN 'sk_label'
WHEN symbol_kind = 13 THEN 'sk_undefined'
WHEN symbol_kind = 14 THEN 'sk_extern_variable'
WHEN symbol_kind = 15 THEN 'sk_extern_function'
WHEN symbol_kind = 16 THEN 'sk_projection'
WHEN symbol_kind = 17 THEN 'sk_overloaded_function'
WHEN symbol_kind = 18 THEN 'sk_parameter'
WHEN symbol_kind = 19 THEN 'sk_class_template'
WHEN symbol_kind = 20 THEN 'sk_function_template'
WHEN symbol_kind = 21 THEN 'sk_variable_template'
WHEN symbol_kind = 22 THEN 'sk_concept_template'
WHEN symbol_kind = 23 THEN 'sk_namespace'
WHEN symbol_kind = 24 THEN 'sk_namespace_projection'
WHEN symbol_kind = 25 THEN 'sk_named_module'
WHEN symbol_kind = 26 THEN 'sk_property_set'
WHEN symbol_kind = 27 THEN 'sk_last'
WHEN symbol_kind = 28 THEN 'sk_nonclass_constructor'
WHEN symbol_kind = 29 THEN 'sk_abstract'
WHEN symbol_kind = 30 THEN 'sk_typeless_parameter'
END AS symbol_kind, CASE WHEN semantic_token_kind = 1 THEN 'none'
WHEN semantic_token_kind = 2 THEN 'macro'
WHEN semantic_token_kind = 3 THEN 'enumerator'
WHEN semantic_token_kind = 4 THEN 'global_variable'
WHEN semantic_token_kind = 5 THEN 'local_variable'
WHEN semantic_token_kind = 6 THEN 'parameter'
WHEN semantic_token_kind = 7 THEN 'type'
WHEN semantic_token_kind = 8 THEN 'ref_type'
WHEN semantic_token_kind = 9 THEN 'value_type'
WHEN semantic_token_kind = 10 THEN 'function'
WHEN semantic_token_kind = 11 THEN 'member_function'
WHEN semantic_token_kind = 12 THEN 'member_field'
WHEN semantic_token_kind = 13 THEN 'static_member_function'
WHEN semantic_token_kind = 14 THEN 'static_member_field'
WHEN semantic_token_kind = 15 THEN 'property'
WHEN semantic_token_kind = 16 THEN 'event'
WHEN semantic_token_kind = 17 THEN 'class_template'
WHEN semantic_token_kind = 18 THEN 'generic_type'
WHEN semantic_token_kind = 19 THEN 'function_template'
WHEN semantic_token_kind = 20 THEN 'namespace'
WHEN semantic_token_kind = 21 THEN 'label'
WHEN semantic_token_kind = 22 THEN 'udl_raw'
WHEN semantic_token_kind = 23 THEN 'udl_number'
WHEN semantic_token_kind = 24 THEN 'udl_string'
WHEN semantic_token_kind = 25 THEN 'operator'
WHEN semantic_token_kind = 26 THEN 'member_operator'
WHEN semantic_token_kind = 27 THEN 'new_delete'
WHEN semantic_token_kind = 28 THEN 'last'
END AS semantic_token_kind
         FROM symbols;
CREATE VIEW symbol_refs_ex AS
         WITH expanded AS (
         SELECT sr.symbol_id, sr.file_id,
                sr.config_id,
                jt.value->>0 AS kind, jt.value->>1 AS offset,
                jt.value->>2 AS length, jt.value->>3 AS attributes
         FROM symbol_refs AS sr
         JOIN shared_data AS refs ON sr.decl_defn_refs = refs.id
         CROSS JOIN json_tree(refs.value) AS jt
         WHERE jt.atom IS NULL and jt.parent IS NOT NULL

         UNION ALL

         SELECT sr.symbol_id, sr.file_id,
                sr.config_id,
                jt.value->>0 AS kind, jt.value->>1 AS offset,
                jt.value->>2 AS length, jt.value->>3 AS attributes
         FROM symbol_refs AS sr
         JOIN shared_data AS refs ON sr.usage_refs = refs.id
         CROSS JOIN json_tree(refs.value) AS jt
         WHERE jt.atom IS NULL and jt.parent IS NOT NULL
        )
        SELECT * FROM expanded;
CREATE VIEW symbol_refs_decl_defn_ex AS
         SELECT sr.symbol_id, sr.file_id,
                sr.config_id, jt.value->>0 AS kind,
                jt.value->>1 AS offset, jt.value->>2 AS length,
                jt.value->>3 AS attributes
         FROM symbol_refs AS sr, json_tree(refs.value) AS jt
         JOIN shared_data AS refs ON sr.decl_defn_refs = refs.id
         WHERE jt.atom IS NULL and jt.parent IS NOT NULL;
CREATE VIEW symbol_refs_debug AS
         SELECT sr.symbol_id, s.declaration AS symbol_declaration,
                s.semantic_token_kind AS symbol_semantic_token_kind,
                sr.file_id, f.leaf_name AS file_leaf_name, sr.config_id,
                concat(replace(p.name, rtrim(p.name,
                                             replace(p.name, '\', '')), ''),
                       ' - ', c.name) AS config_project_name, iif(sr.kind != 0, concat_ws('|', iif(sr.kind & 1 != 0, 'declaration', null), iif(sr.kind & 2 != 0, 'definition', null), iif(sr.kind & 4 != 0, 'reference', null), iif(sr.kind & 8 != 0, 'use', null), iif(sr.kind & 16 != 0, 'modification', null), iif(sr.kind & 2048 != 0, 'initialization', null), iif(sr.kind & 8192 != 0, 'prototype_instantiation_ref', null), iif(sr.kind & 65536 != 0, 'const_value_use', null), iif(sr.kind & 2097152 != 0, 'macro_arg_fixup', null), iif(sr.kind & 4194304 != 0, 'address_of', null), iif(sr.kind & 16777216 != 0, 'using_decl', null), iif(sr.kind & 2147483648 != 0, 'inactive', null)), 'none') AS kind, sr.offset, sr.length, iif(sr.attributes != 0, concat_ws('|', iif(sr.attributes & 1 != 0, 'macro_expansion', null), iif(sr.attributes & 2 != 0, 'has_macro_arg_fixup', null), iif(sr.attributes & 4 != 0, 'destructor_or_finalizer', null), iif(sr.attributes & 8 != 0, 'implicit_call', null), iif(sr.attributes & 16 != 0, 'implicit_instantiation', null), iif(sr.attributes & 32 != 0, 'parent_is_class_template', null), iif(sr.attributes & 64 != 0, 'secondary_position', null)), 'none') AS attributes,
      group_concat(t.file_id || ':' || t.offset || ':' || data.value, ', ')
          AS template_args
      FROM symbol_refs_ex AS sr
      INNER JOIN symbols_debug AS s ON sr.symbol_id = s.id
      INNER JOIN files AS f ON sr.file_id = f.id
      INNER JOIN configs AS c ON sr.config_id = c.id
      INNER JOIN projects AS p ON c.project_id = p.id
      LEFT JOIN template_args AS t ON sr.symbol_id = t.symbol_id
                                      AND sr.config_id = t.config_id
      LEFT JOIN shared_data AS data ON t.args = data.id
      GROUP BY sr.symbol_id, sr.config_id, sr.file_id, sr.offset;
CREATE VIEW symbol_relations_debug AS
         SELECT sr.source_symbol_id, ss.declaration AS source_symbol_declaration,
           sr.target_symbol_id, ts.declaration AS target_symbol_declaration,
           sr.config_id,
           concat(replace(p.name, rtrim(p.name, replace(p.name, '\', '')), ''),
                 ' - ', c.name) AS config_project_name,
           CASE WHEN sr.kind = -1 THEN 'invalid'
WHEN sr.kind = 0 THEN 'derived_of'
WHEN sr.kind = 1 THEN 'base_override_of'
WHEN sr.kind = 2 THEN 'override_of'
WHEN sr.kind = 3 THEN 'direct_override_of'
WHEN sr.kind = 4 THEN 'overload_of'
WHEN sr.kind = 5 THEN 'instantiation_of'
WHEN sr.kind = 6 THEN 'special_function_of'
WHEN sr.kind = 7 THEN 'injected_of'
WHEN sr.kind = 8 THEN 'specialization_of'
END AS kind
         FROM symbol_relations AS sr
         INNER JOIN symbols AS ss ON sr.source_symbol_id = ss.id
         INNER JOIN symbols AS ts ON sr.target_symbol_id = ts.id
         INNER JOIN configs AS c ON sr.config_id = c.id
         INNER JOIN projects AS p ON c.project_id = p.id;
CREATE VIEW symbol_definition_ranges_debug AS
         SELECT sr.symbol_id, s.declaration AS symbol_declaration,
                sr.config_id,
                concat(replace(p.name, rtrim(p.name,
                                             replace(p.name, '\', '')), ''),
                       ' - ', c.name) AS config_project_name,
                sr.file_id, f.leaf_name AS file_leaf_name,
                sr.offset, sr.length
         FROM symbol_definition_ranges AS sr
         INNER JOIN symbols AS s ON sr.symbol_id = s.id
         INNER JOIN files AS f ON sr.file_id = f.id
         INNER JOIN configs AS c ON sr.config_id = c.id
         INNER JOIN projects AS p ON c.project_id = p.id;
CREATE UNIQUE INDEX uq_code_item_kinds_name_parser_guid ON code_item_kinds (name,parser_guid);
CREATE UNIQUE INDEX uq_projects_name ON projects(name);
CREATE UNIQUE INDEX uq_projects_guid ON projects(guid);
CREATE UNIQUE INDEX uq_configs_project_id_name ON configs (project_id,name);
CREATE INDEX ix_configs_name ON configs(name);
CREATE INDEX ix_project_refs_config_id ON project_refs(config_id);
CREATE INDEX ix_project_refs_project_ref_guid ON project_refs(project_ref_guid);
CREATE INDEX ix_files_leaf_name ON files(leaf_name);
CREATE INDEX ix_config_files_file_id ON config_files(file_id);
CREATE INDEX ix_code_items_parent_id_kind ON code_items (parent_id,kind);
CREATE INDEX ix_code_items_name ON code_items(name);
CREATE INDEX ix_code_items_lower_name_hint ON code_items(lower_name_hint);
CREATE INDEX ix_file_map_config_id ON file_map(config_id);
CREATE INDEX ix_file_map_file_id ON file_map(file_id);
CREATE INDEX ix_base_class_parents_parent_code_item_id ON base_class_parents(parent_code_item_id);
CREATE INDEX ix_shared_data_hash ON shared_data(hash);
CREATE INDEX ix_symbol_refs_symbol_id_config_id ON symbol_refs (symbol_id,config_id);
CREATE INDEX ix_symbol_relations_target_symbol_id ON symbol_relations(target_symbol_id);
CREATE INDEX ix_symbol_relations_config_id ON symbol_relations(config_id);
CREATE UNIQUE INDEX uq_file_tu_map_file_id_tu_file_id_config_id ON file_tu_map (file_id,tu_file_id,config_id);
CREATE INDEX ix_file_tu_map_tu_file_id ON file_tu_map(tu_file_id);
CREATE INDEX ix_file_tu_map_config_id ON file_tu_map(config_id);
CREATE INDEX ix_symbol_definition_ranges_file_id_config_id ON symbol_definition_ranges (file_id,config_id);
