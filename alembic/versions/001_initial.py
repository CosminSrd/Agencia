"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear tabla usuarios
    op.create_table(
        'usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('rol', sa.String(length=20), server_default='agente'),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('fecha_creacion', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index('ix_usuarios_username', 'usuarios', ['username'])
    
    # Crear tabla tours
    op.create_table(
        'tours',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(length=300), nullable=False),
        sa.Column('descripcion', sa.Text()),
        sa.Column('destino', sa.String(length=150)),
        sa.Column('origen', sa.String(length=150)),
        sa.Column('precio_desde', sa.Float()),
        sa.Column('precio_hasta', sa.Float()),
        sa.Column('duracion_dias', sa.Integer()),
        sa.Column('imagen_url', sa.String(length=500)),
        sa.Column('mapa_url', sa.String(length=500)),
        sa.Column('proveedor', sa.String(length=100)),
        sa.Column('url_proveedor', sa.String(length=500)),
        sa.Column('categoria', sa.String(length=50)),
        sa.Column('continente', sa.String(length=50)),
        sa.Column('pais', sa.String(length=100)),
        sa.Column('ciudad_salida', sa.String(length=100)),
        sa.Column('tipo_viaje', sa.String(length=50)),
        sa.Column('nivel_confort', sa.String(length=20)),
        sa.Column('temporada_inicio', sa.String(length=20)),
        sa.Column('temporada_fin', sa.String(length=20)),
        sa.Column('incluye', sa.Text()),
        sa.Column('no_incluye', sa.Text()),
        sa.Column('itinerario', sa.Text()),
        sa.Column('num_visitas', sa.Integer(), server_default='0'),
        sa.Column('num_solicitudes', sa.Integer(), server_default='0'),
        sa.Column('slug', sa.String(length=300)),
        sa.Column('keywords', sa.Text()),
        sa.Column('destacado', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('search_vector', postgresql.TSVECTOR()),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('fecha_creacion', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('fecha_actualizacion', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    
    # Crear indices para tours
    op.create_index('ix_tours_destino', 'tours', ['destino'])
    op.create_index('ix_tours_proveedor', 'tours', ['proveedor'])
    op.create_index('ix_tours_continente', 'tours', ['continente'])
    op.create_index('ix_tours_pais', 'tours', ['pais'])
    op.create_index('idx_search_vector', 'tours', ['search_vector'], postgresql_using='gin')
    
    # Pedidos
    op.create_table(
        'pedidos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer()),
        sa.Column('tour_id', sa.Integer()),
        sa.Column('num_personas', sa.Integer(), nullable=False),
        sa.Column('precio_total', sa.Float(), nullable=False),
        sa.Column('estado', sa.String(length=50), server_default='pendiente'),
        sa.Column('fecha_pedido', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('stripe_session_id', sa.String(length=255)),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['tour_id'], ['tours.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_session_id')
    )
    
    # Solicitudes tour
    op.create_table(
        'solicitudes_tour',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tour_id', sa.Integer()),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('apellidos', sa.String(length=100)),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('telefono', sa.String(length=50)),
        sa.Column('num_personas', sa.Integer()),
        sa.Column('fecha_preferida', sa.Date()),
        sa.Column('mensaje', sa.Text()),
        sa.Column('fecha_solicitud', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('estado', sa.String(length=50), server_default='nueva'),
        sa.Column('notas_admin', sa.Text()),
        sa.ForeignKeyConstraint(['tour_id'], ['tours.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('solicitudes_tour')
    op.drop_table('pedidos')
    op.drop_table('tours')
    op.drop_table('usuarios')
