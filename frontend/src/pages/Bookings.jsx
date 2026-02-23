import { Container, Typography } from '@mui/material'

export default function Bookings() {
  return (
    <Container maxWidth="xl">
      <Typography variant="h4" gutterBottom>
        Gestión de Reservas
      </Typography>
      <Typography variant="body1" color="textSecondary">
        Aquí se mostrarán todas las reservas con opciones de filtrado y gestión.
      </Typography>
    </Container>
  )
}
