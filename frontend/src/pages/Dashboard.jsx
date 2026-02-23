import { Container, Grid, Typography, Paper } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { getAdminStats } from '../services/api'

export default function Dashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: getAdminStats,
  })

  if (isLoading) {
    return <div>Cargando...</div>
  }

  return (
    <Container maxWidth="xl">
      <Typography variant="h4" gutterBottom sx={{ mb: 4 }}>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              display: 'flex',
              flexDirection: 'column',
              height: 140,
            }}
          >
            <Typography color="textSecondary" gutterBottom>
              Reservas Hoy
            </Typography>
            <Typography variant="h3">
              {stats?.bookings_today || 0}
            </Typography>
          </Paper>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              display: 'flex',
              flexDirection: 'column',
              height: 140,
            }}
          >
            <Typography color="textSecondary" gutterBottom>
              Ingresos Mes
            </Typography>
            <Typography variant="h3">
              €{stats?.revenue_month || 0}
            </Typography>
          </Paper>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              display: 'flex',
              flexDirection: 'column',
              height: 140,
            }}
          >
            <Typography color="textSecondary" gutterBottom>
              Clientes Activos
            </Typography>
            <Typography variant="h3">
              {stats?.active_customers || 0}
            </Typography>
          </Paper>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              display: 'flex',
              flexDirection: 'column',
              height: 140,
            }}
          >
            <Typography color="textSecondary" gutterBottom>
              Tours Activos
            </Typography>
            <Typography variant="h3">
              {stats?.active_tours || 0}
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  )
}
