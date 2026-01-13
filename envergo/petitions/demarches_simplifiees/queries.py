CHAMP_FRAGMENT = """
fragment ChampFragment on Champ {
  id
  __typename
  label
  stringValue
  ... on DateChamp {
    date
  }
  ... on DatetimeChamp {
    datetime
  }
  ... on CheckboxChamp {
    checked: value
  }
  ... on YesNoChamp {
    selected: value
  }
  ... on DecimalNumberChamp {
    decimalNumber: value
  }
  ... on IntegerNumberChamp {
    integerNumber: value
  }
  ... on CiviliteChamp {
    civilite: value
  }
  ... on LinkedDropDownListChamp {
    primaryValue
    secondaryValue
  }
  ... on MultipleDropDownListChamp {
    values
  }
  ... on PieceJustificativeChamp {
    files {
      ...FileFragment
    }
  }
  ... on AddressChamp {
    address {
      ...AddressFragment
    }
    commune {
      ...CommuneFragment
    }
    departement {
      ...DepartementFragment
    }
  }
  ... on EpciChamp {
    epci {
      ...EpciFragment
    }
    departement {
      ...DepartementFragment
    }
  }
  ... on CommuneChamp {
    commune {
      ...CommuneFragment
    }
    departement {
      ...DepartementFragment
    }
  }
  ... on DepartementChamp {
    departement {
      ...DepartementFragment
    }
  }
  ... on RegionChamp {
    region {
      ...RegionFragment
    }
  }
  ... on PaysChamp {
    pays {
      ...PaysFragment
    }
  }
  ... on SiretChamp {
    etablissement {
      ...PersonneMoraleFragment
    }
  }
  ... on RNFChamp {
    rnf {
      ...RNFFragment
    }
    commune {
      ...CommuneFragment
    }
    departement {
      ...DepartementFragment
    }
  }
  ... on EngagementJuridiqueChamp {
    engagementJuridique {
      ...EngagementJuridiqueFragment
    }
  }
}
"""

PERSONNE_MORALE_FRAGMENT = """
fragment PersonneMoraleFragment on PersonneMorale {
  siret
  siegeSocial
  naf
  libelleNaf
  address {
    ...AddressFragment
  }
  entreprise {
    siren
    capitalSocial
    numeroTvaIntracommunautaire
    formeJuridique
    formeJuridiqueCode
    nomCommercial
    raisonSociale
    siretSiegeSocial
    codeEffectifEntreprise
    dateCreation
    nom
    prenom
    attestationFiscaleAttachment {
      ...FileFragment
    }
    attestationSocialeAttachment {
      ...FileFragment
    }
  }
  association {
    rna
    titre
    objet
    dateCreation
    dateDeclaration
    datePublication
  }
}
"""

PERSONNE_MORALE_INCOMPLETE_FRAGMENT = """
fragment PersonneMoraleIncompleteFragment on PersonneMoraleIncomplete {
  siret
}
"""

PERSONNE_PHYSIQUE_FRAGMENT = """
fragment PersonnePhysiqueFragment on PersonnePhysique {
  civilite
  nom
  prenom
  email
}
"""

FILE_FRAGMENT = """
fragment FileFragment on File {
  __typename
  filename
  contentType
  checksum
  byteSize: byteSizeBigInt
  url
  createdAt
}
"""

ADDRESS_FRAGMENT = """
fragment AddressFragment on Address {
  label
  type
  streetAddress
  streetNumber
  streetName
  postalCode
  cityName
  cityCode
  departmentName
  departmentCode
  regionName
  regionCode
}
"""

PAYS_FRAGMENT = """
fragment PaysFragment on Pays {
  name
  code
}
"""

REGION_FRAGMENT = """
fragment RegionFragment on Region {
  name
  code
}
"""

DEPARTEMENT_FRAGMENT = """
fragment DepartementFragment on Departement {
  name
  code
}
"""

EPCI_FRAGMENT = """
fragment EpciFragment on Epci {
  name
  code
}
"""

COMMUNE_FRAGMENT = """
fragment CommuneFragment on Commune {
  name
  code
  postalCode
}
"""

RNF_FRAGMENT = """
fragment RNFFragment on RNF {
  id
  title
  address {
    ...AddressFragment
  }
}
"""

ENGAGEMENT_JURIDIQUE_FRAGMENT = """
fragment EngagementJuridiqueFragment on EngagementJuridique {
  montantEngage
  montantPaye
}
"""

MESSAGE_FRAGMENT = """
fragment MessageFragment on Message {
  id,
  createdAt,
  email,
  body,
  attachments {
  ...FileFragment
  }
}
"""

DOSSIER_FRAGMENT = (
    (
        CHAMP_FRAGMENT
        + PERSONNE_MORALE_FRAGMENT
        + PERSONNE_MORALE_INCOMPLETE_FRAGMENT
        + PERSONNE_PHYSIQUE_FRAGMENT
        + FILE_FRAGMENT
        + ADDRESS_FRAGMENT
        + PAYS_FRAGMENT
        + REGION_FRAGMENT
        + DEPARTEMENT_FRAGMENT
        + EPCI_FRAGMENT
        + COMMUNE_FRAGMENT
        + RNF_FRAGMENT
        + ENGAGEMENT_JURIDIQUE_FRAGMENT
        + MESSAGE_FRAGMENT
    )
    + """
fragment DossierFragment on Dossier {
  __typename
  id
  number
  archived
  prefilled
  state
  dateDerniereModification
  dateDepot
  motivation
  motivationAttachment {
    ...FileFragment
  }
  attestation {
    ...FileFragment
  }
  pdf {
    ...FileFragment
  }
  usager {
    email
  }
  prenomMandataire
  nomMandataire
  deposeParUnTiers
  demandeur {
    __typename
    ...PersonnePhysiqueFragment
    ...PersonneMoraleFragment
    ...PersonneMoraleIncompleteFragment
  }
  traitements @include(if: $includeTraitements) {
    state
    emailAgentTraitant
    dateTraitement
    motivation
    revision {
      id
      datePublication
    }
  }
  champs @include(if: $includeChamps) {
    ...ChampFragment
  }
  messages @include(if: $includeMessages) {
    ...MessageFragment
  }
  instructeurs {
    email
    id
  }
  demarche {
    title
    number
    revision {
      champDescriptors {
        id
        __typename
        ... on HeaderSectionChampDescriptor {
          label
        }
        ... on ExplicationChampDescriptor {
          label
        }
      }
    }
  }
}
"""
)

GET_DOSSIER_QUERY = (
    DOSSIER_FRAGMENT
    + """
query getDossier(
    $dossierNumber: Int!,
    $includeChamps: Boolean = true,
    $includeTraitements: Boolean = false,
    $includeMessages: Boolean = false
  )
{
  dossier(number: $dossierNumber) {
   ...DossierFragment
  }
}
"""
)

GET_DOSSIERS_FOR_DEMARCHE_QUERY = (
    DOSSIER_FRAGMENT
    + """
query getDossiersForDemarche(
   $demarcheNumber: Int!,
   $updatedSince: ISO8601DateTime,
   $after: String,
   $includeChamps: Boolean = true,
   $includeTraitements: Boolean = false,
   $includeMessages: Boolean = true,
   )
{
   demarche(number: $demarcheNumber)
    {
        title
        number
        dossiers(
            updatedSince: $updatedSince
            after: $after
            )
            {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                ...DossierFragment
                }
            }
    }
}
"""
)
GET_DOSSIER_MESSAGES_QUERY = (
    FILE_FRAGMENT
    + MESSAGE_FRAGMENT
    + """
query getDossier($dossierNumber: Int!)
{
  dossier(number: $dossierNumber) {
    __typename
    id
    number
    archived
    prefilled
    state
    dateDerniereModification
    dateDepot
    instructeurs {
      email
      id
    }
    usager {
      email
    }
    messages {
      ...MessageFragment
    }
  }
}
"""
)

DOSSIER_ENVOYER_MESSAGE_MUTATION = (
    FILE_FRAGMENT
    + MESSAGE_FRAGMENT
    + """
mutation dossierEnvoyerMessage($input: DossierEnvoyerMessageInput!) {
  dossierEnvoyerMessage(input: $input) {
    message {
      ...MessageFragment
    }
    errors {
      message
    }
    clientMutationId
  }
}
"""
)

DOSSIER_CREATE_DIRECT_UPLOAD_MUTATION = """
mutation dossierPreparePiecejointe($input: CreateDirectUploadInput!) {
  createDirectUpload(input: $input) {
    clientMutationId
    directUpload {
      blobId
      headers
      signedBlobId
      url
    }
  }
}
"""

DOSSIER_REPASSER_EN_CONSTRUCTION_MUTATION = (
    DOSSIER_FRAGMENT
    + """
mutation (
$input: DossierRepasserEnConstructionInput!,
 $includeChamps: Boolean = true,
  $includeTraitements: Boolean = false,
  $includeMessages: Boolean = false
  ) {
  dossierRepasserEnConstruction(input: $input) {
    dossier {
    ...DossierFragment
    }
    errors {
      message
    }
  }
}
"""
)

DOSSIER_PASSER_EN_INSTRUCTION_MUTATION = (
    DOSSIER_FRAGMENT
    + """
mutation (
$input: DossierPasserEnInstructionInput!,
 $includeChamps: Boolean = true,
  $includeTraitements: Boolean = false,
  $includeMessages: Boolean = false
  ) {
  dossierPasserEnInstruction(input: $input) {
    dossier {
    ...DossierFragment
    }
    errors {
      message
    }
  }
}
"""
)

DOSSIER_REPASSER_EN_INSTRUCTION_MUTATION = (
    DOSSIER_FRAGMENT
    + """
mutation (
$input: DossierRepasserEnInstructionInput!,
 $includeChamps: Boolean = true,
  $includeTraitements: Boolean = false,
  $includeMessages: Boolean = false
  ) {
  dossierRepasserEnInstruction(input: $input) {
    dossier {
    ...DossierFragment
    }
    errors {
      message
    }
  }
}
"""
)

DOSSIER_ACCEPTER_MUTATION = (
    DOSSIER_FRAGMENT
    + """
mutation (
  $input: DossierAccepterInput!,
  $includeChamps: Boolean = true,
  $includeTraitements: Boolean = false,
  $includeMessages: Boolean = false
) {
  dossierAccepter(input: $input) {
    dossier {
    ...DossierFragment
    }
    errors {
      message
    }
  }
}
"""
)

DOSSIER_REFUSER_MUTATION = (
    DOSSIER_FRAGMENT
    + """
mutation (
  $input: DossierRefuserInput!,
  $includeChamps: Boolean = true,
  $includeTraitements: Boolean = false,
  $includeMessages: Boolean = false
) {
  dossierRefuser(input: $input) {
    dossier {
    ...DossierFragment
    }
    errors {
      message
    }
  }
}
"""
)

DOSSIER_CLASSER_SANS_SUITE_MUTATION = (
    DOSSIER_FRAGMENT
    + """
mutation (
  $input: DossierClasserSansSuiteInput!,
  $includeChamps: Boolean = true,
  $includeTraitements: Boolean = false,
  $includeMessages: Boolean = false
) {
  dossierClasserSansSuite(input: $input) {
    dossier {
    ...DossierFragment
    }
    errors {
      message
    }
  }
}
"""
)
