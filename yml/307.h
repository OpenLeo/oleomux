#include "307_messages.h"

void ole07_parse_commandes_bsi(can_msg* msg, ole07_commandes_bsi* ptr);
void ole07_parse_donnees_bsi_rapides(can_msg* msg, ole07_donnees_bsi_rapides* ptr);
void ole07_parse_donnees_bsi_lentes(can_msg* msg, ole07_donnees_bsi_lentes* ptr);
