import { Container, Typography } from '@mui/material'

export default function Analytics() {
  return (
    <Container maxWidth="xl">
      <Typography variant="h4" gutterBottom>
        Analytics
      </Typography>
      <Typography variant="body1" color="textSecondary">
        Gráficos y estadísticas de ventas, destinos populares, etc.
      </Typography>
    </Container>
  )
}
