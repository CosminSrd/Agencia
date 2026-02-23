"""Add Amadeus fields to reservas_vuelo

Revision ID: 002_add_reservas_vuelo_amadeus_fields
Revises: 001_initial
Create Date: 2026-02-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_reservas_vuelo_amadeus_fields'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reservas_vuelo', sa.Column('provider', sa.String(length=20), server_default='DUFFEL', nullable=True))
    op.add_column('reservas_vuelo', sa.Column('amadeus_order_id', sa.String(length=255), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('amadeus_pnr', sa.String(length=50), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('amadeus_full_offer', sa.Text(), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('amadeus_full_pricing', sa.Text(), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('fecha_validacion_precio', sa.DateTime(), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('lastTicketingDate', sa.String(length=20), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('ticketingAgreement', sa.Text(), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('ticket_numbers', sa.Text(), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('amenities_added', sa.Text(), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('fecha_orden_creada', sa.DateTime(), nullable=True))
    op.add_column('reservas_vuelo', sa.Column('fecha_emision', sa.DateTime(), nullable=True))

    op.create_index('ix_reservas_vuelo_provider', 'reservas_vuelo', ['provider'])
    op.create_index('ix_reservas_vuelo_amadeus_order_id', 'reservas_vuelo', ['amadeus_order_id'])
    op.create_index('ix_reservas_vuelo_amadeus_pnr', 'reservas_vuelo', ['amadeus_pnr'])


def downgrade() -> None:
    op.drop_index('ix_reservas_vuelo_amadeus_pnr', table_name='reservas_vuelo')
    op.drop_index('ix_reservas_vuelo_amadeus_order_id', table_name='reservas_vuelo')
    op.drop_index('ix_reservas_vuelo_provider', table_name='reservas_vuelo')

    op.drop_column('reservas_vuelo', 'fecha_emision')
    op.drop_column('reservas_vuelo', 'fecha_orden_creada')
    op.drop_column('reservas_vuelo', 'amenities_added')
    op.drop_column('reservas_vuelo', 'ticket_numbers')
    op.drop_column('reservas_vuelo', 'ticketingAgreement')
    op.drop_column('reservas_vuelo', 'lastTicketingDate')
    op.drop_column('reservas_vuelo', 'fecha_validacion_precio')
    op.drop_column('reservas_vuelo', 'amadeus_full_pricing')
    op.drop_column('reservas_vuelo', 'amadeus_full_offer')
    op.drop_column('reservas_vuelo', 'amadeus_pnr')
    op.drop_column('reservas_vuelo', 'amadeus_order_id')
    op.drop_column('reservas_vuelo', 'provider')
