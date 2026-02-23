import { Container, Typography } from '@mui/material'

export default function Tours() {
  return (
    <Container maxWidth="xl">
      <Typography variant="h4" gutterBottom>
        Gestión de Tours
      </Typography>
      <Typography variant="body1" color="textSecondary">
        Aquí se mostrará el catálogo de tours con opciones de edición.
      </Typography>
    </Container>
  )
}
