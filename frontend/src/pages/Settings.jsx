import { Container, Typography } from '@mui/material'

export default function Settings() {
  return (
    <Container maxWidth="xl">
      <Typography variant="h4" gutterBottom>
        Configuración
      </Typography>
      <Typography variant="body1" color="textSecondary">
        Configuración de la aplicación (solo admin).
      </Typography>
    </Container>
  )
}
