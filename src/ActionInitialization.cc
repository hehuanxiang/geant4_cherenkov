//
// ActionInitialization.cc
//

#include "ActionInitialization.hh"
#include "PHSPPrimaryGeneratorAction.hh"
#include "RunAction.hh"
#include "EventAction.hh"
#include "SteppingAction.hh"
#include "Config.hh"

ActionInitialization::ActionInitialization()
 : G4VUserActionInitialization()
{}

ActionInitialization::~ActionInitialization()
{}

void ActionInitialization::BuildForMaster() const
{
  RunAction* runAction = new RunAction;
  SetUserAction(runAction);
}

void ActionInitialization::Build() const
{
  // Get PHSP file path from config
  Config* config = Config::GetInstance();
  G4String phspFilePath = config->GetPHSPFilePath();
  
  SetUserAction(new PHSPPrimaryGeneratorAction(phspFilePath));

  RunAction* runAction = new RunAction;
  SetUserAction(runAction);
  
  EventAction* eventAction = new EventAction(runAction);
  SetUserAction(eventAction);
  
  SetUserAction(new SteppingAction(eventAction));
}  
