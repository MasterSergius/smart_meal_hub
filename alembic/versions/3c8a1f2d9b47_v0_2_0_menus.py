"""v0.2.0: meal types, preferences, seasonal produce, menus

Revision ID: 3c8a1f2d9b47
Revises: ef720ce4bfe9
Create Date: 2026-11-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3c8a1f2d9b47'
down_revision: Union[str, None] = 'ef720ce4bfe9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AUTUMN_WINTER = [7, 8, 9, 10, 11, 12, 1, 2, 3]  # harvest plus winter storage

# spec v0.2.0 SEED-2: produce in season in Ukraine, by month. Frozen copy: later
# changes to this data belong in a new migration.
SEASONAL_UA: dict[str, list[int]] = {
    "asparagus": [4, 5, 6],
    "radish": [4, 5, 6, 7, 8, 9],
    "spinach": [4, 5, 6, 9, 10],
    "sorrel": [4, 5, 6, 7],
    "green onion": [4, 5, 6, 7, 8, 9],
    "dill": [5, 6, 7, 8, 9],
    "parsley": [5, 6, 7, 8, 9, 10],
    "strawberry": [5, 6, 7],
    "cherry": [6, 7],
    "raspberry": [6, 7, 8],
    "pea": [6, 7, 8],
    "cucumber": [6, 7, 8, 9],
    "zucchini": [6, 7, 8, 9],
    "blueberry": [7, 8],
    "apricot": [7, 8],
    "tomato": [7, 8, 9],
    "bell pepper": [7, 8, 9, 10],
    "eggplant": [7, 8, 9],
    "corn": [7, 8, 9],
    "cauliflower": [7, 8, 9, 10],
    "broccoli": [7, 8, 9, 10],
    "plum": [8, 9],
    "watermelon": [8, 9],
    "melon": [8, 9],
    "grape": [8, 9, 10],
    "pear": [8, 9, 10],
    "apple": [8, 9, 10, 11, 12],
    "pumpkin": [9, 10, 11],
    "cranberry": [9, 10, 11],
    "cabbage": _AUTUMN_WINTER,
    "beet": _AUTUMN_WINTER,
    "beetroot": _AUTUMN_WINTER,
    "carrot": _AUTUMN_WINTER,
    "garlic": _AUTUMN_WINTER,
    "onion": [7, 8, 9, 10, 11, 12, 1, 2, 3, 4],
    "potato": [7, 8, 9, 10, 11, 12, 1, 2, 3, 4],
}


def upgrade() -> None:
    # ── recipes: meal types (D-6) and normalised diet tags (C-1) ─────────────
    op.add_column('recipes', sa.Column(
        'meal_types', postgresql.ARRAY(sa.String(length=10)),
        server_default=sa.text("'{lunch,dinner}'"), nullable=False,
    ))
    op.create_check_constraint(
        'ck_recipes_meal_types', 'recipes',
        "cardinality(meal_types) >= 1 "
        "AND meal_types <@ ARRAY['breakfast', 'lunch', 'dinner']::varchar[]",
    )
    op.create_index('ix_recipes_meal_types', 'recipes', ['meal_types'], postgresql_using='gin')
    op.create_index('ix_recipes_diet_tags', 'recipes', ['diet_tags'], postgresql_using='gin')
    op.execute(r"""
        UPDATE recipes
        SET diet_tags = ARRAY(
            SELECT DISTINCT lower(regexp_replace(btrim(t), '\s+', ' ', 'g'))
            FROM unnest(diet_tags) AS t
            WHERE btrim(t) <> ''
        )::varchar(50)[]
        WHERE diet_tags IS NOT NULL
    """)

    # ── user_preferences ──────────────────────────────────────────────────────
    op.create_table('user_preferences',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('diets', postgresql.ARRAY(sa.String(length=50)), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('excluded_ingredients', postgresql.ARRAY(sa.String(length=100)), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('household_size', sa.SmallInteger(), server_default=sa.text('2'), nullable=False),
    sa.Column('region', sa.CHAR(length=2), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('household_size BETWEEN 1 AND 20', name='ck_user_preferences_household'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )

    # ── seasonal_produce ──────────────────────────────────────────────────────
    seasonal = op.create_table('seasonal_produce',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('region', sa.CHAR(length=2), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('months', postgresql.ARRAY(sa.SmallInteger()), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('region', 'name', name='uq_seasonal_produce_region_name')
    )
    op.bulk_insert(seasonal, [
        {'region': 'UA', 'name': name, 'months': sorted(months)}
        for name, months in SEASONAL_UA.items()
    ])

    # ── menus + menu_slots ────────────────────────────────────────────────────
    op.create_table('menus',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('servings', sa.SmallInteger(), nullable=False),
    sa.Column('diets', postgresql.ARRAY(sa.String(length=50)), nullable=False),
    sa.Column('excluded_ingredients', postgresql.ARRAY(sa.String(length=100)), nullable=False),
    sa.Column('region', sa.CHAR(length=2), nullable=True),
    sa.Column('seed', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('servings BETWEEN 1 AND 20', name='ck_menus_servings'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_menus_user_id'), 'menus', ['user_id'], unique=False)
    op.create_table('menu_slots',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('menu_id', sa.UUID(), nullable=False),
    sa.Column('day', sa.SmallInteger(), nullable=False),
    sa.Column('meal_type', sa.String(length=10), nullable=False),
    sa.Column('recipe_id', sa.UUID(), nullable=True),
    sa.CheckConstraint('day BETWEEN 1 AND 7', name='ck_menu_slots_day'),
    sa.CheckConstraint("meal_type IN ('breakfast', 'lunch', 'dinner')", name='ck_menu_slots_meal_type'),
    sa.ForeignKeyConstraint(['menu_id'], ['menus.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('menu_id', 'day', 'meal_type', name='uq_menu_slots_menu_day_meal')
    )


def downgrade() -> None:
    # Diet tag normalisation is not reverted: the original spelling is not kept.
    op.drop_table('menu_slots')
    op.drop_index(op.f('ix_menus_user_id'), table_name='menus')
    op.drop_table('menus')
    op.drop_table('seasonal_produce')
    op.drop_table('user_preferences')
    op.drop_index('ix_recipes_diet_tags', table_name='recipes', postgresql_using='gin')
    op.drop_index('ix_recipes_meal_types', table_name='recipes', postgresql_using='gin')
    op.drop_constraint('ck_recipes_meal_types', 'recipes', type_='check')
    op.drop_column('recipes', 'meal_types')
