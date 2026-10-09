"""Adopt the existing beta schema, recovering its legacy pet table without data loss."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    tables = set(sa.inspect(db).get_table_names())
    if 'owner' not in tables:
        op.create_table('owner', sa.Column('id', sa.String(), primary_key=True), sa.Column('email', sa.String(), nullable=False), sa.Column('hashed_password', sa.String(), nullable=False), sa.Column('consent_given_at', sa.DateTime()), sa.Column('created_at', sa.DateTime(), nullable=False))
        op.create_index('ix_owner_email', 'owner', ['email'], unique=True)
    else:
        cols = {c['name'] for c in sa.inspect(db).get_columns('owner')}
        if not {'id', 'email', 'hashed_password', 'created_at'} <= cols:
            raise RuntimeError('Unrecognized owner schema; restore the backup and inspect before migrating')
        if 'consent_given_at' not in cols:
            op.add_column('owner', sa.Column('consent_given_at', sa.DateTime()))
    if 'pet' not in tables:
        op.create_table('pet', sa.Column('id', sa.String(), primary_key=True), sa.Column('owner_id', sa.String(), sa.ForeignKey('owner.id')), sa.Column('name', sa.String(), nullable=False), sa.Column('species', sa.String(4), nullable=False), sa.Column('breed', sa.String()), sa.Column('breed_size', sa.String(6)), sa.Column('date_of_birth', sa.Date()), sa.Column('sex', sa.String(6)), sa.Column('neutered', sa.Boolean()), sa.Column('weight_kg', sa.Float()), sa.Column('environment_factors', sa.JSON()), sa.Column('known_conditions', sa.JSON()))
        op.create_index('ix_pet_owner_id', 'pet', ['owner_id'])
    elif next(c for c in sa.inspect(db).get_columns('pet') if c['name'] == 'owner_id')['nullable'] is False:
        with op.batch_alter_table('pet') as batch:
            batch.alter_column('owner_id', existing_type=sa.String(), nullable=True)
    if 'pet_legacy' in tables:
        # An older startup migration renamed pet, leaving checks attached to pet_legacy.
        meta = sa.MetaData()
        legacy = sa.Table('pet_legacy', meta, autoload_with=db)
        pet = sa.Table('pet', meta, autoload_with=db)
        if set(legacy.c.keys()) != set(pet.c.keys()):
            raise RuntimeError('Legacy pet schema differs; manual reconciliation is required')
        for row in db.execute(sa.select(legacy)).mappings():
            existing = db.execute(sa.select(pet).where(pet.c.id == row['id'])).mappings().first()
            if existing and dict(existing) != dict(row):
                raise RuntimeError('Conflicting legacy pet records; migration stopped without deleting data')
            if not existing:
                db.execute(pet.insert().values(**dict(row)))
    if 'triagesession' not in tables:
        op.create_table('triagesession', sa.Column('id', sa.String(), primary_key=True), sa.Column('pet_id', sa.String(), sa.ForeignKey('pet.id'), nullable=False), sa.Column('started_at', sa.DateTime(), nullable=False), sa.Column('symptom_entry_point', sa.String(), nullable=False), sa.Column('answers_json', sa.String(), nullable=False), sa.Column('current_question_id', sa.String()), sa.Column('resulting_urgency', sa.String(13)), sa.Column('resulting_guidance', sa.String()), sa.Column('condition_entries_matched_raw', sa.String(), nullable=False))
        op.create_index('ix_triagesession_pet_id', 'triagesession', ['pet_id'])
    else:
        cols = {c['name'] for c in sa.inspect(db).get_columns('triagesession')}
        if 'current_question_id' not in cols:
            op.add_column('triagesession', sa.Column('current_question_id', sa.String()))
        fks = sa.inspect(db).get_foreign_keys('triagesession')
        old = [fk for fk in fks if fk['referred_table'] == 'pet_legacy']
        if old:
            with op.batch_alter_table('triagesession', naming_convention={'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}) as batch:
                for fk in old:
                    batch.drop_constraint(fk['name'] or 'fk_triagesession_pet_id_pet_legacy', type_='foreignkey')
                batch.create_foreign_key('fk_triagesession_pet_id_pet', 'pet', ['pet_id'], ['id'])
    for query in ['SELECT COUNT(*) FROM pet WHERE owner_id IS NOT NULL AND owner_id NOT IN (SELECT id FROM owner)', 'SELECT COUNT(*) FROM triagesession WHERE pet_id NOT IN (SELECT id FROM pet)']:
        if db.execute(sa.text(query)).scalar():
            raise RuntimeError('Orphaned records detected; migration stopped. Reconcile the backup before retrying')
    if 'pet_legacy' in tables:
        op.drop_table('pet_legacy')
    for table, column, unique in [('owner', 'email', True), ('pet', 'owner_id', False), ('triagesession', 'pet_id', False)]:
        expected = f'ix_{table}_{column}'
        if expected not in {index['name'] for index in sa.inspect(db).get_indexes(table)}:
            op.create_index(expected, table, [column], unique=unique)


def downgrade():
    # Adopting existing records is intentionally irreversible; roll back using a backup.
    raise RuntimeError('Baseline downgrade is disabled. Restore a verified database backup instead')
