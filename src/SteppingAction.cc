//
// SteppingAction.cc
//

#include "SteppingAction.hh"
#include "EventAction.hh"
#include "Config.hh"

#include "G4Step.hh"
#include "G4Event.hh"
#include "G4RunManager.hh"
#include "G4LogicalVolume.hh"
#include "G4OpticalPhoton.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"

SteppingAction::SteppingAction(EventAction* eventAction)
: G4UserSteppingAction(),
  fEventAction(eventAction)
{}

SteppingAction::~SteppingAction()
{}

void SteppingAction::UserSteppingAction(const G4Step* step)
{
  // Get track information
  G4Track* track = step->GetTrack();
  
  // Only process optical photons
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhotonDefinition()) {
    return;
  }
  
  // Check if this is the first step (photon creation)
  if (track->GetCurrentStepNumber() == 1) {
    // Check if created by Cerenkov process
    const G4VProcess* creatorProcess = track->GetCreatorProcess();
    if (creatorProcess && creatorProcess->GetProcessName() == "Cerenkov") {
      G4StepPoint* preStepPoint = step->GetPreStepPoint();
      G4ThreeVector position = preStepPoint->GetPosition();
      G4ThreeVector direction = preStepPoint->GetMomentumDirection();
      
      fEventAction->RecordPhotonCreation(
        track->GetTrackID(),
        position.x(), position.y(), position.z(),
        direction.x(), direction.y(), direction.z()
      );
    }
  }
  
  // Check if photon is being killed or leaving the water phantom
  G4StepPoint* preStepPoint = step->GetPreStepPoint();
  G4StepPoint* postStepPoint = step->GetPostStepPoint();
  
  // Get volume names
  G4VPhysicalVolume* preVolume = preStepPoint->GetPhysicalVolume();
  G4VPhysicalVolume* postVolume = postStepPoint->GetPhysicalVolume();
  
  G4String preVolName = (preVolume) ? preVolume->GetName() : "None";
  G4String postVolName = (postVolume) ? postVolume->GetName() : "None";
  
  // Get phantom volume name from config
  Config* config = Config::GetInstance();
  G4String phantomName = config->GetPhantomVolumeName();
  
  // Record final state when:
  // 1. Track is killed/absorbed (not alive)
  // 2. Photon leaves phantom (from phantom to non-phantom volume)
  bool isKilled = (track->GetTrackStatus() != fAlive);
  bool leavesPhantom = (preVolName == phantomName && postVolName != phantomName);
  
  if (leavesPhantom) {
    // Record final state at phantom boundary
    G4ThreeVector position = postStepPoint->GetPosition();
    G4ThreeVector direction = postStepPoint->GetMomentumDirection();
    G4double energy = postStepPoint->GetTotalEnergy();
    
    fEventAction->RecordPhotonEnd(
      track->GetTrackID(),
      position.x(), position.y(), position.z(),
      direction.x(), direction.y(), direction.z(),
      energy
    );
    
    // Kill the photon since we're no longer interested in tracking it outside phantom
    track->SetTrackStatus(fStopAndKill);
  }
  else if (isKilled) {
    // Only record if photon is killed inside phantom (not already recorded at boundary)
    if (preVolName == phantomName) {
      G4ThreeVector position = postStepPoint->GetPosition();
      G4ThreeVector direction = postStepPoint->GetMomentumDirection();
      G4double energy = postStepPoint->GetTotalEnergy();
      
      fEventAction->RecordPhotonEnd(
        track->GetTrackID(),
        position.x(), position.y(), position.z(),
        direction.x(), direction.y(), direction.z(),
        energy
      );
    }
  }
}
